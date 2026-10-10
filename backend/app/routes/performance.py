from datetime import datetime
from collections import defaultdict
from fastapi import APIRouter, HTTPException, Body
from app.models.schemas import StudySessionLog, QuizScoreLog
from app.services.scheduler import generate_study_plan
from app.database.mongodb import (
    sessions_collection,
    quizzes_collection,
    study_plans_collection
)

router = APIRouter(prefix="/performance", tags=["Progress & Performance Tracking"])


@router.post("/session")
def log_study_session(session: StudySessionLog):
    """Logs a completed or scheduled study session."""
    data = session.model_dump()
    data["logged_at"] = datetime.utcnow().isoformat()
    if not data.get("date"):
        data["date"] = datetime.utcnow().strftime("%Y-%m-%d")

    if sessions_collection is not None:
        try:
            sessions_collection.insert_one(data)
        except Exception as e:
            print(f"Error logging session: {e}")

    return {"message": "Study session logged successfully", "session": session}


@router.post("/quiz")
def log_quiz_score(quiz: QuizScoreLog):
    """Records a subject quiz score to evaluate learning progress."""
    data = quiz.model_dump()
    data["logged_at"] = datetime.utcnow().isoformat()
    if not data.get("date"):
        data["date"] = datetime.utcnow().strftime("%Y-%m-%d")
    data["percentage"] = round((quiz.score / quiz.total_marks) * 100.0, 1)

    if quizzes_collection is not None:
        try:
            quizzes_collection.insert_one(data)
        except Exception as e:
            print(f"Error logging quiz: {e}")

    return {"message": "Quiz result recorded successfully", "percentage": data["percentage"]}


@router.get("/{email}")
def get_performance_summary(email: str):
    """
    Aggregates student performance metrics:
    - Total study hours and sessions
    - Subject-wise hours and average quiz scores
    - Recent quiz history for progress visualization
    """
    sessions = []
    quizzes = []

    if sessions_collection is not None:
        try:
            sessions = list(sessions_collection.find({"email": email}, {"_id": 0}))
        except Exception:
            pass

    if quizzes_collection is not None:
        try:
            quizzes = list(quizzes_collection.find({"email": email}, {"_id": 0}))
        except Exception:
            pass

    total_study_minutes = sum(s.get("duration_minutes", 0) for s in sessions if s.get("completed", True))
    total_hours = round(total_study_minutes / 60.0, 1)

    # Subject-wise study hours
    subject_hours = defaultdict(float)
    for s in sessions:
        if s.get("completed", True):
            subj = s.get("subject", "General")
            subject_hours[subj] += s.get("duration_minutes", 0) / 60.0

    # Subject-wise quiz average
    subject_quizzes = defaultdict(list)
    for q in quizzes:
        subj = q.get("subject", "General")
        pct = q.get("percentage") or (q.get("score", 0) / q.get("total_marks", 100) * 100.0)
        subject_quizzes[subj].append(pct)

    subject_metrics = []
    all_subjects = set(subject_hours.keys()).union(set(subject_quizzes.keys()))
    for subj in sorted(all_subjects):
        hours = round(subject_hours.get(subj, 0.0), 1)
        quiz_list = subject_quizzes.get(subj, [])
        avg_score = round(sum(quiz_list) / len(quiz_list), 1) if quiz_list else None

        subject_metrics.append({
            "subject": subj,
            "hours_studied": hours,
            "average_quiz_score": avg_score,
            "total_quizzes": len(quiz_list)
        })

    overall_avg_quiz = (
        round(sum(q.get("percentage", 0) for q in quizzes) / len(quizzes), 1)
        if quizzes else None
    )

    return {
        "email": email,
        "total_study_hours": total_hours,
        "total_completed_sessions": len([s for s in sessions if s.get("completed", True)]),
        "overall_average_quiz_score": overall_avg_quiz,
        "subject_metrics": subject_metrics,
        "recent_quizzes": quizzes[-10:],
        "recent_sessions": sessions[-10:]
    }


@router.post("/adapt-plan")
def adapt_study_plan(email: str = Body(..., embed=True)):
    """
    Adapts future study schedules based on newly collected quiz and session data.
    Automatically identifies weak subjects (< 70% quiz average) and boosts their allocation.
    """
    if study_plans_collection is None:
        raise HTTPException(status_code=500, detail="Database unavailable")

    plan_doc = study_plans_collection.find_one({"email": email})
    if not plan_doc or "plan" not in plan_doc:
        raise HTTPException(status_code=404, detail="No existing study plan to adapt. Please generate a plan first.")

    current_plan = plan_doc["plan"]
    subjects = current_plan.get("subjects_weighted", [])

    # Fetch recent quizzes
    quizzes = []
    if quizzes_collection is not None:
        quizzes = list(quizzes_collection.find({"email": email}))

    quiz_scores_by_subject = defaultdict(list)
    for q in quizzes:
        pct = q.get("percentage") or (q.get("score", 0) / q.get("total_marks", 100) * 100.0)
        quiz_scores_by_subject[q.get("subject")].append(pct)

    adapted_subjects = []
    adaptations_made = []

    for subj in subjects:
        subj_name = subj["name"]
        recent_scores = quiz_scores_by_subject.get(subj_name, [])
        new_difficulty = subj.get("difficulty", "Medium")
        new_current = subj.get("current_score", 60.0)

        if recent_scores:
            avg_quiz = sum(recent_scores) / len(recent_scores)
            new_current = round(avg_quiz, 1)

            if avg_quiz < 70.0:
                new_difficulty = "High"
                adaptations_made.append(
                    f"Increased priority for '{subj_name}': Average quiz is {avg_quiz:.1f}% (below 70%)."
                )
            elif avg_quiz >= 85.0:
                new_difficulty = "Low"
                adaptations_made.append(
                    f"Relaxed priority for '{subj_name}': Strong quiz performance of {avg_quiz:.1f}%."
                )

        adapted_subjects.append({
            "name": subj_name,
            "difficulty": new_difficulty,
            "current_score": new_current,
            "target_score": subj.get("target_score", 85.0),
            "exam_date": subj.get("exam_date")
        })

    # Regenerate schedule with adapted parameters
    new_plan = generate_study_plan(
        subjects=adapted_subjects,
        daily_study_hours=current_plan.get("daily_study_hours", 4.0),
        days_to_plan=current_plan.get("days_planned", 7)
    )

    # Save adapted plan
    study_plans_collection.update_one(
        {"email": email},
        {"$set": {
            "plan": new_plan,
            "adapted_at": datetime.utcnow().isoformat(),
            "adaptation_notes": adaptations_made
        }}
    )

    return {
        "message": "Study plan successfully adapted based on latest performance metrics",
        "adaptations": adaptations_made or ["Current study weights remain optimal."],
        "adapted_plan": new_plan
    }
