from datetime import datetime, timezone

from fastapi import APIRouter, Body, Depends, HTTPException

from app.database.mongodb import study_plans_collection
from app.deps.auth import get_current_user, require_owned_email
from app.models.schemas import (
    StudyHourRecommendationRequest,
    StudyHourRecommendationResponse,
    StudyPlanGenerateRequest,
    StudyPlanResponse,
)
from app.services.auth_service import AuthenticatedUser
from app.services.scheduler import generate_study_plan

router = APIRouter(prefix="/study-plan", tags=["Study Plan"])


@router.post("", response_model=StudyPlanResponse)
@router.post("/generate", response_model=StudyPlanResponse)
def generate_plan_endpoint(
    request: StudyPlanGenerateRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Integrates M9 Academic Risk Classification, M10 Study-Hour Recommendations,
    and M11 Deterministic Study Scheduling into a unified Study Plan API (Milestone 12).
    Generates a complete study plan containing recommended daily study hours,
    subject-wise allocations, and the scheduled study timetable.
    """
    try:
        from app.database.mongodb import students_collection, predictions_collection
        from app.services.risk_service import evaluate_academic_risk

        owner = require_owned_email(request.email, current_user)

        # Validate subjects
        if not request.subjects:
            raise ValueError("At least one subject is required to generate a study plan.")
        for s in request.subjects:
            if not s.name or not s.name.strip():
                raise ValueError("Subject name cannot be empty.")

        # Check student profile if daily_available_hours not explicitly set
        avail_hours = request.daily_available_hours
        profile = None
        if students_collection is not None:
            try:
                profile = students_collection.find_one({"email": owner})
                if profile and profile.get("study_hours") and avail_hours is None:
                    avail_hours = float(profile["study_hours"])
            except Exception as pe:
                print(f"Non-fatal error retrieving student profile in study plan: {type(pe).__name__}")

        # Check for prior prediction record in MongoDB if risk category not provided
        recent_pred = None
        risk_cat = request.risk_category
        risk_info = None

        if not risk_cat and predictions_collection is not None:
            try:
                recent_pred = predictions_collection.find_one(
                    {"email": owner},
                    sort=[("created_at", -1)]
                )
            except Exception as pre_err:
                print(f"Non-fatal error retrieving recent prediction: {type(pre_err).__name__}")

        # Dynamically derive risk classification if not provided explicitly
        if not risk_cat:
            if recent_pred and "risk_assessment" in recent_pred:
                risk_info = recent_pred["risk_assessment"]
                risk_cat = risk_info.get("risk_category")
            else:
                att = request.attendance
                prev = request.previous_scores
                pred = request.predicted_exam_score

                if profile:
                    if att is None and profile.get("attendance") is not None:
                        att = float(profile["attendance"])
                    if prev is None and profile.get("previous_cgpa") is not None:
                        cgpa = float(profile["previous_cgpa"])
                        prev = cgpa * 10.0 if cgpa <= 10.0 else cgpa

                if prev is None and request.subjects:
                    scores = [s.current_score for s in request.subjects if s.current_score is not None]
                    if scores:
                        prev = sum(scores) / len(scores)

                if att is not None or prev is not None or pred is not None:
                    effective_avail = (
                        avail_hours if avail_hours is not None
                        else (request.daily_study_hours if request.daily_study_hours is not None else 4.0)
                    )
                    risk_info = evaluate_academic_risk(
                        attendance=att if att is not None else 80.0,
                        hours_studied=effective_avail * 7.0,
                        previous_scores=prev if prev is not None else 75.0,
                        predicted_score=pred if pred is not None else 70.0
                    )
                    risk_cat = risk_info.get("risk_category")

        subjects_data = [s.model_dump() for s in request.subjects]
        plan = generate_study_plan(
            subjects=subjects_data,
            daily_study_hours=request.daily_study_hours,
            preferred_start_time=request.preferred_start_time,
            days_to_plan=request.days_to_plan,
            daily_available_hours=avail_hours,
            risk_category=risk_cat,
            max_daily_limit=request.max_daily_limit,
            plan_date=request.plan_date,
            risk_details=risk_info
        )

        # Persist plan for the authenticated student only
        if study_plans_collection is not None:
            try:
                record = {
                    "email": owner,
                    "plan": plan,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
                study_plans_collection.update_one(
                    {"email": owner},
                    {"$set": record},
                    upsert=True,
                )
            except Exception as db_err:
                print(f"Non-fatal error persisting study plan: {type(db_err).__name__}")

        return plan
    except HTTPException:
        raise
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve)) from ve
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to generate study timetable.") from e


@router.post("/timetable", response_model=StudyPlanResponse)
def generate_timetable_endpoint(
    request: StudyPlanGenerateRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Direct alias endpoint to generate a deterministic daily study timetable (Milestone 11).
    """
    return generate_plan_endpoint(request, current_user)


@router.get("/me")
def get_my_study_plan(current_user: AuthenticatedUser = Depends(get_current_user)):
    return get_student_study_plan(current_user.email, current_user)


@router.get("/{email}")
def get_student_study_plan(
    email: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Fetches the currently active study plan for the authenticated student."""
    owner = require_owned_email(email, current_user)
    if study_plans_collection is None:
        raise HTTPException(
            status_code=503,
            detail="Study plan storage is unavailable because MongoDB is not connected.",
        )

    record = study_plans_collection.find_one({"email": owner}, {"_id": 0})
    if not record:
        return {"message": "No active study plan found", "plan": None, "email": owner}

    return record


@router.put("/{email}/toggle-slot")
def toggle_slot_completion(
    email: str,
    day_key: str = Body(..., embed=True),
    slot_id: str = Body(..., embed=True),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Toggles completion status of a specific slot in the student's weekly study plan."""
    owner = require_owned_email(email, current_user)
    if study_plans_collection is None:
        raise HTTPException(
            status_code=503,
            detail="Study plan storage is unavailable because MongoDB is not connected.",
        )

    record = study_plans_collection.find_one({"email": owner})
    if not record or "plan" not in record:
        raise HTTPException(status_code=404, detail="Study plan not found")

    weekly = record["plan"].get("weekly_schedule", {})
    if day_key in weekly:
        for slot in weekly[day_key]:
            if slot.get("slot_id") == slot_id:
                slot["completed"] = not slot.get("completed", False)
                break

    study_plans_collection.update_one(
        {"email": owner},
        {
            "$set": {
                "plan.weekly_schedule": weekly,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        },
    )

    return {"message": "Slot status updated", "weekly_schedule": weekly, "email": owner}


@router.post("/recommend-hours", response_model=StudyHourRecommendationResponse)
def recommend_study_hours_endpoint(
    request: StudyHourRecommendationRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Computes personalized daily and weekly study hours for the student and per subject
    based on availability, subject difficulty, current vs. goal performance gaps,
    academic risk standing, and daily burnout limits.
    """
    try:
        from app.services.study_hour_recommendation import calculate_study_hour_recommendation
        from app.services.risk_service import evaluate_academic_risk
        from app.database.mongodb import students_collection, predictions_collection

        owner = require_owned_email(request.email, current_user)

        daily_available = request.daily_available_hours
        risk_cat = request.risk_category
        risk_info = None

        profile = None
        if students_collection is not None:
            try:
                profile = students_collection.find_one({"email": owner})
                if profile and profile.get("study_hours") and request.daily_available_hours == 4.0:
                    daily_available = float(profile["study_hours"])
            except Exception as pe:
                print(f"Non-fatal error retrieving student profile: {type(pe).__name__}")

        # Check for prior prediction record in MongoDB if risk category not provided
        recent_pred = None
        if not risk_cat and predictions_collection is not None:
            try:
                recent_pred = predictions_collection.find_one(
                    {"email": owner},
                    sort=[("created_at", -1)]
                )
            except Exception as pre_err:
                print(f"Non-fatal error retrieving recent prediction: {type(pre_err).__name__}")

        # Dynamically derive risk classification if not provided explicitly
        if not risk_cat:
            if recent_pred and "risk_assessment" in recent_pred:
                risk_info = recent_pred["risk_assessment"]
                risk_cat = risk_info.get("risk_category")
            else:
                att = request.attendance
                prev = request.previous_scores
                pred = request.predicted_exam_score

                if profile:
                    if att is None and profile.get("attendance") is not None:
                        att = float(profile["attendance"])
                    if prev is None and profile.get("previous_cgpa") is not None:
                        cgpa = float(profile["previous_cgpa"])
                        prev = cgpa * 10.0 if cgpa <= 10.0 else cgpa

                if prev is None and request.subjects:
                    scores = [s.current_score for s in request.subjects if s.current_score is not None]
                    if scores:
                        prev = sum(scores) / len(scores)

                if att is not None or prev is not None or pred is not None:
                    risk_info = evaluate_academic_risk(
                        attendance=att if att is not None else 80.0,
                        hours_studied=daily_available * 7.0,
                        previous_scores=prev if prev is not None else 75.0,
                        predicted_score=pred if pred is not None else 70.0
                    )
                    risk_cat = risk_info.get("risk_category")

        subjects_payload = [s.model_dump() for s in request.subjects]

        recommendation = calculate_study_hour_recommendation(
            daily_available_hours=daily_available,
            subjects=subjects_payload,
            risk_category=risk_cat,
            max_daily_limit=request.max_daily_limit,
            risk_details=risk_info
        )

        return recommendation
    except HTTPException:
        raise
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve)) from ve
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail="Failed to calculate study hour recommendation.",
        ) from e
