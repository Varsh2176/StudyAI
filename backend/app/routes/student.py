from fastapi import APIRouter
from app.models.schemas import StudentProfile
from app.database.mongodb import students_collection

router = APIRouter(prefix="/student", tags=["Student"])


@router.post("/profile")
def create_profile(profile: StudentProfile):

    existing_profile = students_collection.find_one({
        "email": profile.email
    })

    if existing_profile:
        students_collection.update_one(
            {"email": profile.email},
            {"$set": profile.model_dump()}
        )

        return {
            "message": "Profile updated successfully"
        }

    students_collection.insert_one(
        profile.model_dump()
    )

    return {
        "message": "Profile created successfully"
    }


@router.get("/{email}")
def get_profile(email: str):

    profile = students_collection.find_one(
        {"email": email},
        {"_id": 0}
    )

    if profile is None:
        return {
            "message": "Profile not found"
        }

    return profile