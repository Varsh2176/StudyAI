from fastapi import APIRouter, Depends, HTTPException

from app.database.mongodb import students_collection
from app.deps.auth import get_current_user, require_owned_email
from app.models.schemas import StudentProfile
from app.services.auth_service import AuthenticatedUser

router = APIRouter(prefix="/student", tags=["Student"])


def _require_students_collection():
    if students_collection is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "Student profile storage is unavailable because MongoDB is not connected. "
                "In-memory fallback is not used for profiles. Check /health/database."
            ),
        )


@router.post("/profile")
def create_profile(
    profile: StudentProfile,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    _require_students_collection()
    owner = require_owned_email(profile.email, current_user)
    data = profile.model_dump()
    data["email"] = owner

    try:
        existing_profile = students_collection.find_one({"email": owner})

        if existing_profile:
            students_collection.update_one({"email": owner}, {"$set": data})
            return {
                "message": "Profile updated successfully",
                "persistence": "mongo",
                "email": owner,
            }

        students_collection.insert_one(data)
        return {
            "message": "Profile created successfully",
            "persistence": "mongo",
            "email": owner,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "Could not save student profile because MongoDB is unreachable. "
                f"({type(exc).__name__}). Check /health/database for the failure stage."
            ),
        ) from exc


@router.get("/me")
def get_my_profile(current_user: AuthenticatedUser = Depends(get_current_user)):
    return get_profile(current_user.email, current_user)


@router.get("/{email}")
def get_profile(
    email: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    _require_students_collection()
    owner = require_owned_email(email, current_user)

    try:
        profile = students_collection.find_one({"email": owner}, {"_id": 0})
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "Could not load student profile because MongoDB is unreachable. "
                f"({type(exc).__name__}). Check /health/database for the failure stage."
            ),
        ) from exc

    if profile is None:
        return {"message": "Profile not found", "email": owner}

    return profile
