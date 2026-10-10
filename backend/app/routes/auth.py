from fastapi import APIRouter
from pydantic import BaseModel
from app.database.mongodb import users_collection

router = APIRouter(prefix="/auth", tags=["Authentication"])


class RegisterUser(BaseModel):
    name: str
    email: str
    password: str


@router.post("/register")
def register(user: RegisterUser):

    existing_user = users_collection.find_one({
        "email": user.email
    })

    if existing_user:
        return {
            "message": "User already exists"
        }

    user_data = {
        "name": user.name,
        "email": user.email,
        "password": user.password
    }

    users_collection.insert_one(user_data)

    return {
        "message": "Registration successful"
    }