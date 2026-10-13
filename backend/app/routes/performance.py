"""
M17/M18 — Progress tracking and adaptive planning routes.

Sessions and quizzes persist in MongoDB only. When Mongo is unavailable,
endpoints return 503 with a clear message (no silent in-memory success).

M10: ownership is the authenticated token subject. Client-supplied emails
must match the token or the request is rejected with 403.
"""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from app.database.mongodb import (
    quizzes_collection,
    sessions_collection,
    study_plans_collection,
)
from app.deps.auth import get_current_user, require_owned_email
from app.models.schemas import AdaptPlanRequest, QuizScoreLog, StudySessionLog
from app.services.adaptive_planning_service import (
    AdaptivePlanningError,
    adapt_plan_from_progress,
)
from app.services.auth_service import AuthenticatedUser
from app.services.progress_service import (
    ProgressError,
    build_progress_summary,
    normalize_student_email,
    resolve_session_fields,
    validate_session_date,
)

router = APIRouter(prefix="/performance", tags=["Progress & Performance Tracking"])


def _require_sessions_collection():
    if sessions_collection is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "Progress storage is unavailable because MongoDB is not connected. "
                "Session data is not kept in memory. Check /health/database."
            ),
        )


def _require_quizzes_collection():
    if quizzes_collection is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "Quiz storage is unavailable because MongoDB is not connected. "
                "Check /health/database."
            ),
        )


def _http_from_progress_error(exc: ProgressError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.message)


@router.post("/session")
def log_study_session(
    session: StudySessionLog,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Create a study session progress record for the authenticated student.
    status: completed | partial | missed. Tracks planned vs actual minutes.
    """
    _require_sessions_collection()
    owner = require_owned_email(session.email, current_user)

    try:
        payload = session.model_dump()
        payload["email"] = owner
        record = resolve_session_fields(payload)
    except ProgressError as exc:
        raise _http_from_progress_error(exc) from exc

    try:
        sessions_collection.insert_one(dict(record))
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "Could not save study session because MongoDB is unreachable. "
                f"({type(exc).__name__}). Check /health/database."
            ),
        ) from exc

    safe = {k: v for k, v in record.items() if k != "_id"}
    return {
        "message": "Study session logged successfully",
        "persistence": "mongo",
        "session": safe,
    }


@router.get("/{email}/sessions")
def list_study_sessions(
    email: str,
    status: Optional[str] = None,
    limit: int = 50,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """List study sessions owned by the authenticated student."""
    _require_sessions_collection()
    owner = require_owned_email(email, current_user)

    try:
        owner = normalize_student_email(owner)
    except ProgressError as exc:
        raise _http_from_progress_error(exc) from exc

    try:
        limit_n = int(limit)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="limit must be an integer.") from exc
    if limit_n < 1 or limit_n > 200:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 200.")

    query = {"email": owner}
    if status:
        status_norm = status.strip().lower()
        if status_norm not in {"completed", "partial", "missed"}:
            raise HTTPException(
                status_code=400,
                detail="status filter must be completed, partial, or missed.",
            )
        query["status"] = status_norm

    try:
        cursor = (
            sessions_collection.find(query, {"_id": 0})
            .sort([("date", -1), ("logged_at", -1)])
            .limit(limit_n)
        )
        sessions = list(cursor)
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "Could not load study sessions because MongoDB is unreachable. "
                f"({type(exc).__name__}). Check /health/database."
            ),
        ) from exc

    # Defense in depth — never return another student's rows
    sessions = [s for s in sessions if (s.get("email") or "").lower() == owner]

    return {
        "email": owner,
        "count": len(sessions),
        "sessions": sessions,
        "persistence": "mongo",
        "empty": len(sessions) == 0,
    }


@router.post("/quiz")
def log_quiz_score(
    quiz: QuizScoreLog,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Records a subject quiz score owned by the authenticated student."""
    _require_quizzes_collection()
    owner = require_owned_email(quiz.email, current_user)

    try:
        owner = normalize_student_email(owner)
        quiz_date = validate_session_date(quiz.date)
    except ProgressError as exc:
        raise _http_from_progress_error(exc) from exc

    if quiz.score > quiz.total_marks:
        raise HTTPException(
            status_code=400,
            detail="score cannot be greater than total_marks.",
        )

    data = quiz.model_dump()
    data["email"] = owner
    data["date"] = quiz_date
    data["logged_at"] = datetime.now(timezone.utc).isoformat()
    data["percentage"] = round((quiz.score / quiz.total_marks) * 100.0, 1)
    data["persistence"] = "mongo"

    try:
        quizzes_collection.insert_one(dict(data))
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "Could not save quiz score because MongoDB is unreachable. "
                f"({type(exc).__name__}). Check /health/database."
            ),
        ) from exc

    return {
        "message": "Quiz result recorded successfully",
        "percentage": data["percentage"],
        "persistence": "mongo",
        "email": owner,
    }


@router.get("/{email}")
def get_performance_summary(
    email: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Aggregates student progress for the authenticated student only:
    - Completed / partial / missed session counts
    - Planned versus actual study hours
    - Subject-wise progress and completion rates
    """
    _require_sessions_collection()
    owner = require_owned_email(email, current_user)

    try:
        owner = normalize_student_email(owner)
    except ProgressError as exc:
        raise _http_from_progress_error(exc) from exc

    try:
        sessions = list(sessions_collection.find({"email": owner}, {"_id": 0}))
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "Could not load progress because MongoDB is unreachable. "
                f"({type(exc).__name__}). Check /health/database."
            ),
        ) from exc

    quizzes = []
    if quizzes_collection is not None:
        try:
            quizzes = list(quizzes_collection.find({"email": owner}, {"_id": 0}))
        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail=(
                    "Could not load quiz history because MongoDB is unreachable. "
                    f"({type(exc).__name__}). Check /health/database."
                ),
            ) from exc

    return build_progress_summary(email=owner, sessions=sessions, quizzes=quizzes)


@router.post("/adapt-plan")
def adapt_study_plan(
    request: AdaptPlanRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    M18: Adapt the stored study plan from M17 session progress (and quizzes).
    Reschedules unfinished work into a future horizon without exceeding daily limits.
    Repeat-safe: identical progress does not increase workload again.
    Historical session records are never modified or deleted.
    """
    if study_plans_collection is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "Study plan storage is unavailable because MongoDB is not connected. "
                "Check /health/database."
            ),
        )
    _require_sessions_collection()
    owner = require_owned_email(request.email, current_user)

    try:
        owner = normalize_student_email(owner)
    except ProgressError as exc:
        raise _http_from_progress_error(exc) from exc

    try:
        plan_doc = study_plans_collection.find_one({"email": owner})
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "Could not load study plan because MongoDB is unreachable. "
                f"({type(exc).__name__}). Check /health/database."
            ),
        ) from exc

    if not plan_doc or "plan" not in plan_doc:
        raise HTTPException(
            status_code=404,
            detail="No existing study plan to adapt. Please generate a plan first.",
        )

    try:
        sessions = list(sessions_collection.find({"email": owner}, {"_id": 0}))
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "Could not load study sessions because MongoDB is unreachable. "
                f"({type(exc).__name__}). Check /health/database."
            ),
        ) from exc

    quizzes = []
    if quizzes_collection is not None:
        try:
            quizzes = list(quizzes_collection.find({"email": owner}, {"_id": 0}))
        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail=(
                    "Could not load quizzes because MongoDB is unreachable. "
                    f"({type(exc).__name__}). Check /health/database."
                ),
            ) from exc

    try:
        result = adapt_plan_from_progress(
            email=owner,
            plan_document=plan_doc,
            sessions=sessions,
            quizzes=quizzes,
            daily_available_hours=request.daily_available_hours,
            days_to_plan=request.days_to_plan,
            plan_date=request.plan_date,
            max_daily_limit=request.max_daily_limit,
        )
    except AdaptivePlanningError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    except ProgressError as exc:
        raise _http_from_progress_error(exc) from exc

    if result.get("unchanged"):
        return result

    history_entry = {
        "adapted_at": result["adapted_at"],
        "adaptation_fingerprint": result["adaptation_fingerprint"],
        "adaptations": result.get("adaptations") or [],
    }
    prior_history = list(plan_doc.get("adaptation_history") or [])
    prior_history.append(history_entry)
    prior_history = prior_history[-20:]

    try:
        study_plans_collection.update_one(
            {"email": owner},
            {
                "$set": {
                    "email": owner,
                    "plan": result["adapted_plan"],
                    "adapted_at": result["adapted_at"],
                    "adaptation_notes": result.get("adaptations") or [],
                    "adaptation_fingerprint": result["adaptation_fingerprint"],
                    "adaptation_history": prior_history,
                    "declared_daily_study_hours": result.get("declared_daily_study_hours"),
                    "declared_days_to_plan": result.get("declared_days_to_plan"),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
            },
        )
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "Could not save adapted plan because MongoDB is unreachable. "
                f"({type(exc).__name__}). Check /health/database."
            ),
        ) from exc

    return result
