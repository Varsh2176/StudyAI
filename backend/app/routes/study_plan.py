from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Body
from app.models.schemas import StudyPlanGenerateRequest, StudyHourRecommendationRequest, StudyHourRecommendationResponse
from app.services.scheduler import generate_study_plan
from app.database.mongodb import study_plans_collection

router = APIRouter(prefix="/study-plan", tags=["Study Plan"])


@router.post("/generate")
def generate_plan_endpoint(request: StudyPlanGenerateRequest):
    """
    Deterministically computes a personalized daily and weekly study plan
    based on student study hours, subject difficulty, exam dates, and score gaps.
    """
    subjects_data = [s.model_dump() for s in request.subjects]
    plan = generate_study_plan(
        subjects=subjects_data,
        daily_study_hours=request.daily_study_hours,
        preferred_start_time=request.preferred_start_time,
        days_to_plan=request.days_to_plan
    )

    # If student email is provided, save or update their active plan in MongoDB
    if request.email and study_plans_collection is not None:
        try:
            record = {
                "email": request.email,
                "plan": plan,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
            study_plans_collection.update_one(
                {"email": request.email},
                {"$set": record},
                upsert=True
            )
        except Exception as db_err:
            print(f"Non-fatal error persisting study plan: {db_err}")

    return plan


@router.get("/{email}")
def get_student_study_plan(email: str):
    """Fetches the currently active study plan for a student."""
    if study_plans_collection is None:
        return {"plan": None}

    record = study_plans_collection.find_one({"email": email}, {"_id": 0})
    if not record:
        return {"message": "No active study plan found", "plan": None}

    return record


@router.put("/{email}/toggle-slot")
def toggle_slot_completion(
    email: str,
    day_key: str = Body(..., embed=True),
    slot_id: str = Body(..., embed=True)
):
    """Toggles completion status of a specific slot in the student's weekly study plan."""
    if study_plans_collection is None:
        return {"message": "Database unavailable"}

    record = study_plans_collection.find_one({"email": email})
    if not record or "plan" not in record:
        raise HTTPException(status_code=404, detail="Study plan not found")

    weekly = record["plan"].get("weekly_schedule", {})
    if day_key in weekly:
        for slot in weekly[day_key]:
            if slot.get("slot_id") == slot_id:
                slot["completed"] = not slot.get("completed", False)
                break

    study_plans_collection.update_one(
        {"email": email},
        {"$set": {"plan.weekly_schedule": weekly, "updated_at": datetime.now(timezone.utc).isoformat()}}
    )

    return {"message": "Slot status updated", "weekly_schedule": weekly}


@router.post("/recommend-hours", response_model=StudyHourRecommendationResponse)
def recommend_study_hours_endpoint(request: StudyHourRecommendationRequest):
    """
    Computes personalized daily and weekly study hours for the student and per subject
    based on availability, subject difficulty, current vs. goal performance gaps,
    academic risk standing, and daily burnout limits.
    """
    try:
        from app.services.study_hour_recommendation import calculate_study_hour_recommendation
        from app.database.mongodb import students_collection

        daily_available = request.daily_available_hours

        # Optionally check existing profile if student email provided
        if request.email and students_collection is not None:
            try:
                profile = students_collection.find_one({"email": request.email})
                # If available hours was not explicitly tweaked or profile exists
                if profile and profile.get("study_hours") and request.daily_available_hours == 4.0:
                    daily_available = float(profile["study_hours"])
            except Exception:
                pass

        subjects_payload = [s.model_dump() for s in request.subjects]

        recommendation = calculate_study_hour_recommendation(
            daily_available_hours=daily_available,
            subjects=subjects_payload,
            risk_category=request.risk_category,
            max_daily_limit=request.max_daily_limit
        )

        return recommendation
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to calculate study hour recommendation: {str(e)}")
