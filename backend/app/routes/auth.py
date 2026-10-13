"""
M10 — Registration and login with hashed passwords + bearer access tokens.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.database.mongodb import users_collection
from app.deps.auth import get_current_user
from app.services.auth_service import (
    AuthConfigError,
    AuthenticatedUser,
    create_access_token,
    hash_password,
    normalize_email,
    validate_password_strength,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


class RegisterUser(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    email: str = Field(..., min_length=3, max_length=254)
    password: str = Field(..., min_length=1, max_length=128)


class LoginUser(BaseModel):
    email: str = Field(..., min_length=3, max_length=254)
    password: str = Field(..., min_length=1, max_length=128)


def _require_users_collection():
    if users_collection is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "Authentication storage is unavailable because MongoDB is not connected. "
                "In-memory registration is disabled. Check /health/database."
            ),
        )


def _public_auth_response(message: str, token_payload: dict) -> dict:
    return {
        "message": message,
        "persistence": "mongo",
        "access_token": token_payload["access_token"],
        "token_type": token_payload["token_type"],
        "expires_in": token_payload["expires_in"],
        "expires_at": token_payload["expires_at"],
        "email": token_payload["email"],
        "name": token_payload["name"],
        "warning": None,
    }


@router.post("/register")
def register(user: RegisterUser):
    _require_users_collection()

    try:
        email = normalize_email(user.email)
        name = user.name.strip()
        if not name:
            raise ValueError("Name is required.")
        validate_password_strength(user.password)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    try:
        existing = users_collection.find_one({"email": email})
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Registration service temporarily unavailable. Please try again shortly.",
        ) from exc

    if existing:
        raise HTTPException(
            status_code=409,
            detail="A student with this email is already registered. Please sign in.",
        )

    try:
        password_hash = hash_password(user.password)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    record = {
        "name": name,
        "email": email,
        "password_hash": password_hash,
        # Never store plaintext password.
    }

    try:
        users_collection.insert_one(record)
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Could not save registration. Database is temporarily unavailable.",
        ) from exc

    try:
        token_payload = create_access_token(email=email, name=name)
    except AuthConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return _public_auth_response("Registration successful", token_payload)


@router.post("/login")
def login(user: LoginUser):
    _require_users_collection()

    try:
        email = normalize_email(user.email)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    try:
        record = users_collection.find_one({"email": email})
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Login service temporarily unavailable. Please try again shortly.",
        ) from exc

    password_hash = (record or {}).get("password_hash") or ""
    # Also reject legacy plaintext `password` field — never verify against it.
    if not record or not verify_password(user.password, password_hash):
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password.",
        )

    name = str(record.get("name") or email.split("@")[0]).strip()
    try:
        token_payload = create_access_token(email=email, name=name)
    except AuthConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return _public_auth_response("Login successful", token_payload)


@router.get("/me")
def auth_me(current_user: AuthenticatedUser = Depends(get_current_user)):
    return {
        "email": current_user.email,
        "name": current_user.name,
        "authenticated": True,
    }


@router.post("/logout")
def logout(current_user: AuthenticatedUser = Depends(get_current_user)):
    """
    Stateless tokens cannot be revoked server-side without a denylist.
    Clients must discard the access token. This endpoint confirms the session was valid.
    """
    return {
        "message": "Signed out. Discard the access token on the client.",
        "email": current_user.email,
    }
