"""
M17 — Progress tracking helpers.

Aggregates planned vs actual study time and session completion rates
from MongoDB-backed session records. No in-memory permanent store.
"""

from __future__ import annotations

import re
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
VALID_STATUSES = frozenset({"completed", "partial", "missed"})


class ProgressError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def normalize_student_email(email: Optional[str]) -> str:
    value = (email or "").strip().lower()
    if not value or "@" not in value or "." not in value.split("@")[-1]:
        raise ProgressError("A valid student email is required.", status_code=400)
    return value


def validate_session_date(date_str: Optional[str]) -> str:
    if not date_str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")
    value = str(date_str).strip()
    if not DATE_RE.fullmatch(value):
        raise ProgressError("date must be YYYY-MM-DD.", status_code=400)
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise ProgressError("date is not a valid calendar date.", status_code=400) from exc
    return value


def resolve_session_fields(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize a StudySessionLog-like dict into a persistent session record.
    Supports legacy clients that send only duration_minutes / completed.
    """
    email = normalize_student_email(payload.get("email"))
    subject = (payload.get("subject") or "").strip()
    if not subject:
        raise ProgressError("subject is required.", status_code=400)

    topic = (payload.get("topic") or "").strip()
    status = (payload.get("status") or "").strip().lower()

    # Legacy completed flag → status when status missing/invalid
    if status not in VALID_STATUSES:
        completed_flag = payload.get("completed")
        if completed_flag is False:
            status = "missed"
        else:
            status = "completed"

    planned = payload.get("planned_minutes")
    if planned is None:
        planned = 50
    try:
        planned_minutes = int(planned)
    except (TypeError, ValueError) as exc:
        raise ProgressError("planned_minutes must be an integer.", status_code=400) from exc
    if planned_minutes < 1 or planned_minutes > 600:
        raise ProgressError("planned_minutes must be between 1 and 600.", status_code=400)

    actual_raw = payload.get("actual_minutes")
    if actual_raw is None:
        actual_raw = payload.get("duration_minutes")

    if status == "missed":
        actual_minutes = 0 if actual_raw is None else int(actual_raw)
        if actual_minutes != 0:
            # Missed sessions have no credited study time
            actual_minutes = 0
    else:
        if actual_raw is None:
            # Default actual to planned for completed; half for partial
            actual_minutes = planned_minutes if status == "completed" else max(1, planned_minutes // 2)
        else:
            try:
                actual_minutes = int(actual_raw)
            except (TypeError, ValueError) as exc:
                raise ProgressError("actual_minutes must be an integer.", status_code=400) from exc

    if actual_minutes < 0 or actual_minutes > 600:
        raise ProgressError("actual_minutes must be between 0 and 600.", status_code=400)

    if status == "completed" and actual_minutes <= 0:
        raise ProgressError("completed sessions require actual_minutes > 0.", status_code=400)
    if status == "partial" and actual_minutes <= 0:
        raise ProgressError("partial sessions require actual_minutes > 0.", status_code=400)

    session_date = validate_session_date(payload.get("date"))
    notes = payload.get("notes")
    if notes is not None:
        notes = str(notes).strip()[:500] or None

    session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    return {
        "session_id": session_id,
        "email": email,
        "subject": subject,
        "topic": topic,
        "status": status,
        "planned_minutes": planned_minutes,
        "actual_minutes": actual_minutes,
        # Legacy mirrors for older summary consumers
        "duration_minutes": actual_minutes,
        "completed": status == "completed",
        "date": session_date,
        "notes": notes,
        "logged_at": now,
        "persistence": "mongo",
    }


def build_progress_summary(
    *,
    email: str,
    sessions: List[Dict[str, Any]],
    quizzes: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Aggregate progress metrics scoped to one student email."""
    owner = normalize_student_email(email)
    quizzes = quizzes or []

    # Ownership hard filter (defense in depth if caller passes mixed lists)
    owned_sessions = [
        s for s in sessions
        if (s.get("email") or "").strip().lower() == owner
    ]
    owned_quizzes = [
        q for q in quizzes
        if (q.get("email") or "").strip().lower() == owner
    ]

    status_counts = {"completed": 0, "partial": 0, "missed": 0}
    planned_total = 0
    actual_total = 0

    subject_stats: Dict[str, Dict[str, Any]] = defaultdict(
        lambda: {
            "subject": "",
            "planned_minutes": 0,
            "actual_minutes": 0,
            "completed": 0,
            "partial": 0,
            "missed": 0,
            "sessions": 0,
        }
    )

    for session in owned_sessions:
        status = (session.get("status") or "").lower()
        if status not in VALID_STATUSES:
            status = "completed" if session.get("completed", True) else "missed"

        planned = int(session.get("planned_minutes") or session.get("duration_minutes") or 0)
        if status == "missed":
            actual = 0
        else:
            actual = int(
                session.get("actual_minutes")
                if session.get("actual_minutes") is not None
                else (session.get("duration_minutes") or 0)
            )

        status_counts[status] = status_counts.get(status, 0) + 1
        planned_total += max(0, planned)
        actual_total += max(0, actual)

        subject = (session.get("subject") or "General").strip() or "General"
        bucket = subject_stats[subject]
        bucket["subject"] = subject
        bucket["planned_minutes"] += max(0, planned)
        bucket["actual_minutes"] += max(0, actual)
        bucket[status] = bucket.get(status, 0) + 1
        bucket["sessions"] += 1

    total_sessions = len(owned_sessions)
    completed_or_partial = status_counts["completed"] + status_counts["partial"]
    completion_rate = (
        round((status_counts["completed"] / total_sessions) * 100.0, 1)
        if total_sessions
        else 0.0
    )
    attendance_rate = (
        round((completed_or_partial / total_sessions) * 100.0, 1)
        if total_sessions
        else 0.0
    )

    subject_metrics = []
    for subject in sorted(subject_stats.keys()):
        bucket = subject_stats[subject]
        sess_n = bucket["sessions"] or 1
        subject_metrics.append({
            "subject": subject,
            "planned_hours": round(bucket["planned_minutes"] / 60.0, 2),
            "actual_hours": round(bucket["actual_minutes"] / 60.0, 2),
            "hours_studied": round(bucket["actual_minutes"] / 60.0, 2),
            "sessions_total": bucket["sessions"],
            "sessions_completed": bucket["completed"],
            "sessions_partial": bucket["partial"],
            "sessions_missed": bucket["missed"],
            "completion_rate_percent": round((bucket["completed"] / sess_n) * 100.0, 1),
            "average_quiz_score": None,
            "total_quizzes": 0,
        })

    # Merge quiz averages into subject metrics
    subject_quizzes: Dict[str, List[float]] = defaultdict(list)
    for quiz in owned_quizzes:
        subj = (quiz.get("subject") or "General").strip() or "General"
        pct = quiz.get("percentage")
        if pct is None:
            total = float(quiz.get("total_marks") or 100) or 100.0
            pct = (float(quiz.get("score") or 0) / total) * 100.0
        subject_quizzes[subj].append(float(pct))

    known = {m["subject"] for m in subject_metrics}
    for subj, scores in subject_quizzes.items():
        avg = round(sum(scores) / len(scores), 1) if scores else None
        if subj in known:
            for metric in subject_metrics:
                if metric["subject"] == subj:
                    metric["average_quiz_score"] = avg
                    metric["total_quizzes"] = len(scores)
        else:
            subject_metrics.append({
                "subject": subj,
                "planned_hours": 0.0,
                "actual_hours": 0.0,
                "hours_studied": 0.0,
                "sessions_total": 0,
                "sessions_completed": 0,
                "sessions_partial": 0,
                "sessions_missed": 0,
                "completion_rate_percent": 0.0,
                "average_quiz_score": avg,
                "total_quizzes": len(scores),
            })

    subject_metrics.sort(key=lambda m: m["subject"])

    overall_avg_quiz = (
        round(
            sum(
                q.get("percentage")
                if q.get("percentage") is not None
                else (float(q.get("score") or 0) / (float(q.get("total_marks") or 100) or 100) * 100.0)
                for q in owned_quizzes
            )
            / len(owned_quizzes),
            1,
        )
        if owned_quizzes
        else None
    )

    # Newest first for recent lists
    def _sort_key(item: Dict[str, Any]) -> Tuple[str, str]:
        return (str(item.get("date") or ""), str(item.get("logged_at") or ""))

    recent_sessions = sorted(owned_sessions, key=_sort_key, reverse=True)[:15]
    recent_quizzes = sorted(owned_quizzes, key=_sort_key, reverse=True)[:10]

    return {
        "email": owner,
        "persistence": "mongo",
        "total_sessions": total_sessions,
        "sessions_completed": status_counts["completed"],
        "sessions_partial": status_counts["partial"],
        "sessions_missed": status_counts["missed"],
        "total_completed_sessions": status_counts["completed"],
        "completion_rate_percent": completion_rate,
        "attendance_rate_percent": attendance_rate,
        "planned_study_hours": round(planned_total / 60.0, 2),
        "actual_study_hours": round(actual_total / 60.0, 2),
        "total_study_hours": round(actual_total / 60.0, 2),
        "planned_versus_actual": {
            "planned_minutes": planned_total,
            "actual_minutes": actual_total,
            "delta_minutes": actual_total - planned_total,
            "fulfillment_percent": (
                round((actual_total / planned_total) * 100.0, 1) if planned_total else 0.0
            ),
        },
        "overall_average_quiz_score": overall_avg_quiz,
        "subject_metrics": subject_metrics,
        "recent_sessions": [
            {
                "session_id": s.get("session_id"),
                "subject": s.get("subject"),
                "topic": s.get("topic"),
                "status": s.get("status") or ("completed" if s.get("completed", True) else "missed"),
                "planned_minutes": s.get("planned_minutes"),
                "actual_minutes": s.get("actual_minutes", s.get("duration_minutes")),
                "date": s.get("date"),
                "notes": s.get("notes"),
            }
            for s in recent_sessions
        ],
        "recent_quizzes": recent_quizzes,
        "empty": total_sessions == 0 and len(owned_quizzes) == 0,
    }
