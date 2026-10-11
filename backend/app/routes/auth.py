from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.database.mongodb import users_collection

router = APIRouter(prefix="/auth", tags=["Authentication"])

# Temporary process-local fallback ONLY when MongoDB operations fail.
# Not a production datastore — callers are warned when this path is used.
_users_fallback = {}

MEMORY_WARNING = (
    "MongoDB is unreachable. This registration was saved in temporary in-memory storage "
    "for this API process only and will be lost when the server restarts. "
    "Student profile and other MongoDB-backed features may still fail until Atlas connectivity is restored."
)


class RegisterUser(BaseModel):
    name: str = Field(..., min_length=1)
    email: str = Field(..., min_length=3)
    password: str = Field(..., min_length=1)


def _lookup_user(email: str):
    """Return (user_dict_or_None, source) where source is 'mongo' or 'memory'."""
    if users_collection is not None:
        try:
            found = users_collection.find_one({"email": email})
            return found, "mongo"
        except Exception as exc:
            print(f"Warning: MongoDB user lookup failed: {type(exc).__name__}")
    return _users_fallback.get(email.lower()), "memory"


def _insert_user(user_data: dict) -> str:
    """
    Prefer MongoDB. If unavailable, store in memory and return 'memory'.
    Never pretends memory storage is durable Mongo persistence.
    """
    if users_collection is not None:
        try:
            users_collection.insert_one(dict(user_data))
            return "mongo"
        except Exception as exc:
            print(f"Warning: MongoDB user insert failed: {type(exc).__name__}")

    email_key = user_data["email"].lower()
    _users_fallback[email_key] = {
        "name": user_data["name"],
        "email": user_data["email"],
        "password": user_data["password"],
    }
    return "memory"


@router.post("/register")
def register(user: RegisterUser):
    email = user.email.strip()
    name = user.name.strip()
    password = user.password

    if not name or not email or not password:
        raise HTTPException(status_code=422, detail="Name, email, and password are required.")

    try:
        existing_user, _source = _lookup_user(email)
    except Exception:
        raise HTTPException(
            status_code=503,
            detail="Registration service temporarily unavailable. Please try again shortly.",
        )

    if existing_user:
        return {
            "message": "User already exists",
            "persistence": "unknown",
            "warning": None,
        }

    user_data = {
        "name": name,
        "email": email,
        "password": password
    }

    try:
        persistence = _insert_user(user_data)
    except Exception:
        raise HTTPException(
            status_code=503,
            detail="Could not save registration. Database is temporarily unavailable.",
        )

    response = {
        "message": "Registration successful",
        "persistence": persistence,
        "warning": MEMORY_WARNING if persistence == "memory" else None,
    }
    return response
