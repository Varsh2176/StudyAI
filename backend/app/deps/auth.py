"""
M10 — Authentication dependencies and ownership helpers.

Never treat client-supplied email as proof of identity.
"""

from __future__ import annotations

from typing import Optional

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.services.auth_service import (
    AuthenticatedUser,
    InvalidTokenError,
    decode_access_token,
    normalize_email,
)

_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> AuthenticatedUser:
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Sign in and include Authorization: Bearer <token>.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        return decode_access_token(credentials.credentials)
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=401,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def require_owned_email(
    requested_email: Optional[str],
    current_user: AuthenticatedUser,
) -> str:
    """
    Return the authenticated student's email.
    If the client also supplied an email, it must match the token subject.
    """
    owner = current_user.email
    if requested_email is None:
        return owner
    raw = str(requested_email).strip()
    if not raw:
        return owner
    try:
        requested = normalize_email(raw)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if requested != owner:
        raise HTTPException(
            status_code=403,
            detail="You are not allowed to access another student's data.",
        )
    return owner
