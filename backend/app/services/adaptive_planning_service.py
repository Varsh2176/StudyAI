"""
M18 — Adaptive study planning from recorded progress.

Uses M17 session progress (completed / partial / missed) and planned-vs-actual
time to adjust subject priorities, then regenerates a future timetable via the
existing M11 scheduler. Never mutates historical session records.

Repeat-safe: identical progress fingerprints do not increase workload again.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.services.progress_service import ProgressError, build_progress_summary, normalize_student_email
from app.services.scheduler import generate_study_plan


# Cap unfinished work redistributed into future days (fraction of total future capacity).
MAX_BACKLOG_FRACTION_OF_HORIZON = 0.25
# Never raise daily study hours above the student's declared limit during adaptation.
DIFFICULTY_RANK = {"low": 0, "medium": 1, "high": 2}
DIFFICULTY_LABELS = ["Low", "Medium", "High"]


class AdaptivePlanningError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _parse_plan_date(value: Optional[str], default: Optional[datetime] = None) -> datetime:
    if value:
        try:
            return datetime.strptime(str(value).strip(), "%Y-%m-%d")
        except ValueError as exc:
            raise AdaptivePlanningError("plan_date must be YYYY-MM-DD.", status_code=400) from exc
    return default or datetime.now()


def compute_adaptation_fingerprint(
    *,
    email: str,
    sessions: List[Dict[str, Any]],
    quizzes: List[Dict[str, Any]],
    daily_available_hours: float,
    days_to_plan: int,
    plan_date: str,
    subject_names: List[str],
) -> str:
    """
    Stable hash of progress + adaptation constraints.
    Uses request/availability inputs — not mutated plan fields — so a successful
    adaptation does not change the fingerprint and re-trigger workload growth.
    """
    owner = normalize_student_email(email)
    session_parts = []
    for s in sessions:
        if (s.get("email") or "").lower() != owner:
            continue
        session_parts.append(
            (
                s.get("session_id") or "",
                (s.get("subject") or "").strip().lower(),
                (s.get("status") or "").lower(),
                int(s.get("planned_minutes") or 0),
                int(s.get("actual_minutes") if s.get("actual_minutes") is not None else (s.get("duration_minutes") or 0)),
                s.get("date") or "",
            )
        )
    session_parts.sort()

    quiz_parts = []
    for q in quizzes:
        if (q.get("email") or "").lower() != owner:
            continue
        quiz_parts.append(
            (
                (q.get("subject") or "").strip().lower(),
                round(float(q.get("score") or 0), 2),
                round(float(q.get("total_marks") or 100), 2),
                q.get("date") or q.get("logged_at") or "",
            )
        )
    quiz_parts.sort()

    payload = {
        "email": owner,
        "sessions": session_parts,
        "quizzes": quiz_parts,
        "daily_available_hours": round(float(daily_available_hours), 2),
        "days_to_plan": int(days_to_plan),
        "plan_date": str(plan_date),
        "subjects": sorted(n.strip().lower() for n in subject_names if n),
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def compute_subject_backlog_minutes(
    *,
    email: str,
    sessions: List[Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    """
    Unfinished work per subject from missed (full planned) and partial (planned - actual).
    Completed sessions contribute zero backlog.
    """
    owner = normalize_student_email(email)
    by_subject: Dict[str, Dict[str, Any]] = defaultdict(
        lambda: {
            "backlog_minutes": 0,
            "missed": 0,
            "partial": 0,
            "completed": 0,
            "planned_minutes": 0,
            "actual_minutes": 0,
        }
    )

    for session in sessions:
        if (session.get("email") or "").lower() != owner:
            continue
        subject = (session.get("subject") or "General").strip() or "General"
        status = (session.get("status") or "").lower()
        if status not in {"completed", "partial", "missed"}:
            status = "completed" if session.get("completed", True) else "missed"

        planned = max(0, int(session.get("planned_minutes") or session.get("duration_minutes") or 0))
        if status == "missed":
            actual = 0
            deficit = planned
        else:
            actual = max(
                0,
                int(
                    session.get("actual_minutes")
                    if session.get("actual_minutes") is not None
                    else (session.get("duration_minutes") or 0)
                ),
            )
            deficit = max(0, planned - actual) if status == "partial" else 0

        bucket = by_subject[subject]
        bucket["planned_minutes"] += planned
        bucket["actual_minutes"] += actual
        bucket[status] = bucket.get(status, 0) + 1
        bucket["backlog_minutes"] += deficit

    return dict(by_subject)


def _bump_difficulty(current: str, steps: int = 1) -> str:
    rank = DIFFICULTY_RANK.get(str(current or "Medium").lower(), 1)
    new_rank = max(0, min(2, rank + steps))
    return DIFFICULTY_LABELS[new_rank]


def _drop_difficulty(current: str, steps: int = 1) -> str:
    return _bump_difficulty(current, steps=-steps)


def build_adapted_subjects(
    *,
    plan_subjects: List[Dict[str, Any]],
    backlog_by_subject: Dict[str, Dict[str, Any]],
    quizzes: List[Dict[str, Any]],
    email: str,
) -> Tuple[List[Dict[str, Any]], List[str], Dict[str, int]]:
    """
    Adjust difficulty / current_score from progress + quizzes.
    Returns adapted subject inputs for generate_study_plan, explanation notes,
    and capped backlog minutes used for weighting (not raw dump of all deficit).
    """
    owner = normalize_student_email(email)
    quiz_by_subject: Dict[str, List[float]] = defaultdict(list)
    for q in quizzes:
        if (q.get("email") or "").lower() != owner:
            continue
        subj = (q.get("subject") or "").strip()
        if not subj:
            continue
        pct = q.get("percentage")
        if pct is None:
            total = float(q.get("total_marks") or 100) or 100.0
            pct = (float(q.get("score") or 0) / total) * 100.0
        quiz_by_subject[subj].append(float(pct))

    reasons: List[str] = []
    adapted: List[Dict[str, Any]] = []
    capped_backlog: Dict[str, int] = {}

    for subj in plan_subjects:
        name = (subj.get("name") or "").strip()
        if not name:
            continue

        difficulty = str(subj.get("difficulty") or "Medium")
        try:
            current_score = float(subj.get("current_score", 60.0))
        except (TypeError, ValueError):
            current_score = 60.0
        try:
            target_score = float(subj.get("target_score", 85.0))
        except (TypeError, ValueError):
            target_score = 85.0
        exam_date = subj.get("exam_date")

        stats = backlog_by_subject.get(name, {})
        backlog = int(stats.get("backlog_minutes") or 0)
        missed = int(stats.get("missed") or 0)
        partial = int(stats.get("partial") or 0)
        completed = int(stats.get("completed") or 0)
        planned = int(stats.get("planned_minutes") or 0)
        actual = int(stats.get("actual_minutes") or 0)
        sessions_n = missed + partial + completed

        # Cap per-subject backlog influence (keep scheduling realistic)
        capped = min(backlog, 120)  # at most ~2 hours of catch-up weight per subject
        capped_backlog[name] = capped

        if missed > 0:
            difficulty = _bump_difficulty(difficulty, 1)
            reasons.append(
                f"Raised priority for '{name}': {missed} missed session(s) "
                f"left ~{backlog} min of unfinished work."
            )
        elif partial > 0 and backlog > 0:
            difficulty = _bump_difficulty(difficulty, 1 if backlog >= 20 else 0)
            reasons.append(
                f"Adjusted '{name}' for partial completion "
                f"({actual}/{planned} min studied; ~{backlog} min remaining)."
            )

        if sessions_n > 0:
            completion_rate = (completed / sessions_n) * 100.0
            if completion_rate < 50.0 and missed + partial > 0:
                # Softly widen score gap so scheduler allocates more slots
                current_score = max(0.0, current_score - min(10.0, 3.0 * (missed + partial)))
                reasons.append(
                    f"'{name}' completion rate is {completion_rate:.0f}%; "
                    f"future allocation increased within daily limits."
                )
            elif completion_rate >= 80.0 and backlog == 0 and completed >= 2:
                difficulty = _drop_difficulty(difficulty, 1)
                reasons.append(
                    f"Relaxed '{name}' slightly after strong completion "
                    f"({completion_rate:.0f}% of logged sessions completed)."
                )

        quiz_scores = quiz_by_subject.get(name, [])
        if quiz_scores:
            avg_quiz = sum(quiz_scores) / len(quiz_scores)
            current_score = round(0.5 * current_score + 0.5 * avg_quiz, 1)
            if avg_quiz < 70.0:
                difficulty = _bump_difficulty(difficulty, 1)
                reasons.append(
                    f"Increased priority for '{name}': quiz average {avg_quiz:.1f}% is below 70%."
                )
            elif avg_quiz >= 85.0 and backlog == 0:
                difficulty = _drop_difficulty(difficulty, 1)
                reasons.append(
                    f"Relaxed '{name}': strong quiz average of {avg_quiz:.1f}%."
                )

        # Extra priority nudge from capped backlog via score gap (bounded)
        if capped > 0:
            current_score = max(0.0, current_score - min(8.0, capped / 30.0))

        adapted.append({
            "name": name,
            "difficulty": difficulty,
            "current_score": round(max(0.0, min(100.0, current_score)), 1),
            "target_score": round(max(0.0, min(100.0, target_score)), 1),
            "exam_date": exam_date,
        })

    # Upcoming exams already handled inside calculate_subject_weights via exam_date
    exam_notes = []
    for subj in adapted:
        if subj.get("exam_date"):
            try:
                exam_dt = datetime.strptime(str(subj["exam_date"]), "%Y-%m-%d").date()
                days_left = (exam_dt - datetime.now().date()).days
                if 0 <= days_left <= 14:
                    exam_notes.append(
                        f"Upcoming exam for '{subj['name']}' in {days_left} day(s) "
                        f"increases urgency in the adapted schedule."
                    )
            except ValueError:
                pass
    # Deduplicate reasons while preserving order
    seen = set()
    unique_reasons = []
    for note in reasons + exam_notes:
        if note not in seen:
            seen.add(note)
            unique_reasons.append(note)

    return adapted, unique_reasons, capped_backlog


def adapt_plan_from_progress(
    *,
    email: str,
    plan_document: Dict[str, Any],
    sessions: List[Dict[str, Any]],
    quizzes: Optional[List[Dict[str, Any]]] = None,
    daily_available_hours: Optional[float] = None,
    days_to_plan: Optional[int] = None,
    plan_date: Optional[str] = None,
    max_daily_limit: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Produce an adapted future plan from progress. Does not modify sessions.
    Repeat-safe when the progress fingerprint matches the last adaptation.
    """
    owner = normalize_student_email(email)
    quizzes = quizzes or []

    current_plan = plan_document.get("plan")
    if not current_plan:
        raise AdaptivePlanningError(
            "No existing study plan to adapt. Generate a plan first.",
            status_code=404,
        )

    plan_subjects = current_plan.get("subjects_weighted") or []
    # subjects_weighted may use "name"; also accept raw subject list shape
    if plan_subjects and "name" not in plan_subjects[0] and "subject" in plan_subjects[0]:
        plan_subjects = [
            {
                "name": s.get("subject") or s.get("name"),
                "difficulty": s.get("difficulty", "Medium"),
                "current_score": s.get("current_score", 60.0),
                "target_score": s.get("target_score", 85.0),
                "exam_date": s.get("exam_date"),
            }
            for s in plan_subjects
        ]

    if not plan_subjects:
        raise AdaptivePlanningError(
            "Stored study plan has no subjects to adapt.",
            status_code=400,
        )

    # Preserve the student's originally declared daily hours across adaptations
    # so fingerprints stay stable when the request omits daily_available_hours.
    try:
        declared_daily = float(
            plan_document.get("declared_daily_study_hours")
            or current_plan.get("declared_daily_study_hours")
            or current_plan.get("daily_study_hours")
            or 4.0
        )
    except (TypeError, ValueError):
        declared_daily = 4.0

    try:
        base_daily = float(
            daily_available_hours if daily_available_hours is not None else declared_daily
        )
    except (TypeError, ValueError) as exc:
        raise AdaptivePlanningError("daily_available_hours must be a number.", status_code=400) from exc

    if base_daily <= 0 or base_daily > 16:
        raise AdaptivePlanningError(
            "daily_available_hours must be between 0.5 and 16.",
            status_code=400,
        )

    horizon = int(
        days_to_plan
        if days_to_plan is not None
        else plan_document.get("declared_days_to_plan")
        or current_plan.get("days_planned", 7)
    )
    if horizon < 1 or horizon > 30:
        raise AdaptivePlanningError("days_to_plan must be between 1 and 30.", status_code=400)

    # Start adapted horizon tomorrow so historical days are not rewritten as "new" work
    if plan_date:
        anchor = _parse_plan_date(plan_date)
    else:
        anchor = datetime.now() + timedelta(days=1)
    plan_date_str = anchor.strftime("%Y-%m-%d")

    subject_names = [(s.get("name") or "").strip() for s in plan_subjects]
    fingerprint = compute_adaptation_fingerprint(
        email=owner,
        sessions=sessions,
        quizzes=quizzes,
        daily_available_hours=base_daily,
        days_to_plan=horizon,
        plan_date=plan_date_str,
        subject_names=subject_names,
    )

    previous_fp = plan_document.get("adaptation_fingerprint")
    previous_plan = plan_document.get("plan")
    if previous_fp == fingerprint and plan_document.get("adapted_at") and previous_plan:
        progress = build_progress_summary(email=owner, sessions=sessions, quizzes=quizzes)
        return {
            "email": owner,
            "unchanged": True,
            "repeat_safe": True,
            "message": (
                "No new progress since the last adaptation. "
                "The plan was left unchanged to avoid duplicating catch-up workload."
            ),
            "adaptations": [
                "Repeat adaptation skipped: progress fingerprint unchanged.",
            ],
            "adaptation_fingerprint": fingerprint,
            "adapted_at": plan_document.get("adapted_at"),
            "adapted_plan": previous_plan,
            "progress_snapshot": {
                "sessions_completed": progress.get("sessions_completed"),
                "sessions_partial": progress.get("sessions_partial"),
                "sessions_missed": progress.get("sessions_missed"),
                "planned_versus_actual": progress.get("planned_versus_actual"),
                "empty": progress.get("empty"),
            },
            "persistence": "mongo",
            "identity_note": (
                "This API scopes data by the supplied student email, matching the rest of "
                "StudyWise AI. Email alone is not cryptographic proof of identity."
            ),
        }

    backlog_by_subject = compute_subject_backlog_minutes(email=owner, sessions=sessions)
    adapted_subjects, reasons, capped_backlog = build_adapted_subjects(
        plan_subjects=plan_subjects,
        backlog_by_subject=backlog_by_subject,
        quizzes=quizzes,
        email=owner,
    )

    progress = build_progress_summary(email=owner, sessions=sessions, quizzes=quizzes)
    if progress.get("empty"):
        reasons = [
            "No logged study sessions yet; plan priorities refreshed from stored subjects "
            "and quiz history only."
        ] + reasons

    total_backlog = sum(int(v.get("backlog_minutes") or 0) for v in backlog_by_subject.values())
    horizon_capacity_min = int(base_daily * 60 * horizon)
    max_redistribute = int(horizon_capacity_min * MAX_BACKLOG_FRACTION_OF_HORIZON)
    if total_backlog > max_redistribute:
        reasons.append(
            f"Unfinished work totals ~{total_backlog} min; only a bounded share "
            f"(≤{max_redistribute} min across the horizon, ~{int(MAX_BACKLOG_FRACTION_OF_HORIZON*100)}% of "
            f"available capacity) influences priorities so the daily limit stays realistic."
        )

    # Declared daily limit is never increased by adaptation
    effective_daily = min(base_daily, declared_daily)
    if daily_available_hours is not None and float(daily_available_hours) < declared_daily:
        reasons.append(
            f"Available study time reduced to {effective_daily:.1f} h/day "
            f"(was {declared_daily:.1f} h); schedule compressed to fit."
        )

    daily_cap = float(
        max_daily_limit
        if max_daily_limit is not None
        else current_plan.get("max_daily_limit", 8.0)
    )

    try:
        new_plan = generate_study_plan(
            subjects=adapted_subjects,
            daily_study_hours=effective_daily,
            preferred_start_time=current_plan.get("preferred_start_time", "09:00"),
            days_to_plan=horizon,
            daily_available_hours=effective_daily,
            risk_category=current_plan.get("risk_category_applied"),
            max_daily_limit=daily_cap,
            plan_date=plan_date_str,
            risk_details=current_plan.get("risk_assessment_details"),
        )
    except ValueError as exc:
        raise AdaptivePlanningError(str(exc), status_code=400) from exc

    new_plan["adaptation"] = {
        "adapted_from_progress": True,
        "adaptation_fingerprint": fingerprint,
        "plan_date": plan_date_str,
        "backlog_minutes_by_subject": {
            k: int(v.get("backlog_minutes") or 0) for k, v in backlog_by_subject.items()
        },
        "capped_backlog_minutes_by_subject": capped_backlog,
        "reasons": reasons or ["Priorities refreshed; no major progress gaps detected."],
        "historical_sessions_preserved": True,
    }

    adapted_at = datetime.now(timezone.utc).isoformat()
    if not reasons:
        reasons = ["Priorities refreshed; no major progress gaps detected."]

    return {
        "email": owner,
        "unchanged": False,
        "repeat_safe": True,
        "message": "Study plan adapted from recorded progress without modifying past sessions.",
        "adaptations": reasons,
        "adaptation_fingerprint": fingerprint,
        "adapted_at": adapted_at,
        "declared_daily_study_hours": declared_daily,
        "declared_days_to_plan": horizon,
        "adapted_plan": new_plan,
        "progress_snapshot": {
            "sessions_completed": progress.get("sessions_completed"),
            "sessions_partial": progress.get("sessions_partial"),
            "sessions_missed": progress.get("sessions_missed"),
            "planned_versus_actual": progress.get("planned_versus_actual"),
            "completion_rate_percent": progress.get("completion_rate_percent"),
            "empty": progress.get("empty"),
        },
        "persistence": "mongo",
        "identity_note": (
            "This API scopes data by the supplied student email, matching the rest of "
            "StudyWise AI. Email alone is not cryptographic proof of identity."
        ),
    }
