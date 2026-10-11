from fastapi import APIRouter, HTTPException
from app.models.schemas import StudentProfile
from app.database.mongodb import students_collection

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
def create_profile(profile: StudentProfile):
    _require_students_collection()

    try:
        existing_profile = students_collection.find_one({
            "email": profile.email
        })

        if existing_profile:
            students_collection.update_one(
                {"email": profile.email},
                {"$set": profile.model_dump()}
            )
            return {
                "message": "Profile updated successfully",
                "persistence": "mongo",
            }

        students_collection.insert_one(
            profile.model_dump()
        )
        return {
            "message": "Profile created successfully",
            "persistence": "mongo",
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


@router.get("/{email}")
def get_profile(email: str):
    _require_students_collection()

    try:
        profile = students_collection.find_one(
            {"email": email},
            {"_id": 0}
        )
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "Could not load student profile because MongoDB is unreachable. "
                f"({type(exc).__name__}). Check /health/database for the failure stage."
            ),
        ) from exc

    if profile is None:
        return {
            "message": "Profile not found"
        }

    return profile
