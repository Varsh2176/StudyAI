"""
M10 — Password hashing and short-lived access tokens.

Uses stdlib only:
- hashlib.scrypt for password hashes (never store plaintext)
- HMAC-SHA256 bearer tokens (JWT-like compact payload)

Identity for student data must come from a validated token, not client-supplied email.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional


# scrypt parameters (interactive login cost)
_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1
_SCRYPT_DKLEN = 32
_HASH_PREFIX = "scrypt"

DEFAULT_ACCESS_TOKEN_MINUTES = 60
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128
MIN_PRODUCTION_JWT_SECRET_LENGTH = 32

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Reject known placeholders even if an operator copies .env.example into production.
_WEAK_JWT_SECRETS = frozenset(
    s.lower()
    for s in (
        "",
        "your_secret_key_here",
        "replace_me_before_enabling_jwt",
        "replace_with_a_long_random_secret",
        "studyai-dev-only-jwt-secret-change-me",
        "secret",
        "changeme",
        "change-me",
        "jwt_secret",
    )
)


class AuthError(Exception):
    """Base auth error."""


class AuthConfigError(AuthError):
    """Raised when JWT/auth secrets are missing in a way that blocks issuance."""


class InvalidCredentialsError(AuthError):
    """Invalid email/password (do not reveal which)."""


class InvalidTokenError(AuthError):
    """Missing, malformed, expired, or tampered access token."""


@dataclass(frozen=True)
class AuthenticatedUser:
    email: str
    name: str
    exp: int
    iat: int

    def to_public_dict(self) -> Dict[str, Any]:
        return {"email": self.email, "name": self.name}


def normalize_email(email: str) -> str:
    value = (email or "").strip().lower()
    if not value or not _EMAIL_RE.match(value):
        raise ValueError("A valid email address is required.")
    return value


def validate_password_strength(password: str) -> None:
    if password is None or not isinstance(password, str):
        raise ValueError("Password is required.")
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
    if len(password) > MAX_PASSWORD_LENGTH:
        raise ValueError(f"Password must be at most {MAX_PASSWORD_LENGTH} characters.")
    if password.strip() != password:
        raise ValueError("Password cannot start or end with whitespace.")
    if password.isspace():
        raise ValueError("Password cannot be blank.")
    # Require mixed character classes without forcing special characters (usability).
    has_letter = any(ch.isalpha() for ch in password)
    has_digit = any(ch.isdigit() for ch in password)
    if not has_letter or not has_digit:
        raise ValueError("Password must include at least one letter and one number.")


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def hash_password(password: str) -> str:
    """Return a salted scrypt hash string. Never log or return the plaintext."""
    validate_password_strength(password)
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
        dklen=_SCRYPT_DKLEN,
    )
    return (
        f"{_HASH_PREFIX}${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}$"
        f"{_b64encode(salt)}${_b64encode(digest)}"
    )


def verify_password(password: str, password_hash: str) -> bool:
    """
    Constant-ish time verify against a scrypt hash.
    Legacy plaintext rows (pre-M10) never verify successfully — users must re-register.
    """
    if not password or not password_hash or not isinstance(password_hash, str):
        return False
    if not password_hash.startswith(f"{_HASH_PREFIX}$"):
        # Refuse plaintext / unknown formats (no silent migration of insecure storage).
        return False
    try:
        _prefix, n_s, r_s, p_s, salt_b64, hash_b64 = password_hash.split("$", 5)
        n, r, p = int(n_s), int(r_s), int(p_s)
        salt = _b64decode(salt_b64)
        expected = _b64decode(hash_b64)
        actual = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=n,
            r=r,
            p=p,
            dklen=len(expected),
        )
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


def _app_env_name() -> str:
    return (os.getenv("APP_ENV") or os.getenv("ENVIRONMENT") or "development").strip().lower()


def is_production_env() -> bool:
    return _app_env_name() in {"production", "prod"}


def get_jwt_secret() -> str:
    secret = (os.getenv("JWT_SECRET") or "").strip()
    weak = (not secret) or (secret.lower() in _WEAK_JWT_SECRETS) or (len(secret) < 16)
    if not weak:
        if is_production_env() and len(secret) < MIN_PRODUCTION_JWT_SECRET_LENGTH:
            raise AuthConfigError(
                f"JWT_SECRET must be at least {MIN_PRODUCTION_JWT_SECRET_LENGTH} characters in production."
            )
        return secret
    # Dev fallback — never use an empty secret. Operators must set JWT_SECRET in production.
    if is_production_env():
        raise AuthConfigError(
            "JWT_SECRET must be set to a strong random value in production."
        )
    return "studyai-dev-only-jwt-secret-change-me"


def get_access_token_expire_minutes() -> int:
    raw = os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", str(DEFAULT_ACCESS_TOKEN_MINUTES))
    try:
        value = int(raw)
        return max(5, min(value, 24 * 60))
    except (TypeError, ValueError):
        return DEFAULT_ACCESS_TOKEN_MINUTES


def create_access_token(*, email: str, name: str, expires_minutes: Optional[int] = None) -> Dict[str, Any]:
    owner = normalize_email(email)
    display_name = (name or "").strip() or owner.split("@")[0]
    minutes = expires_minutes if expires_minutes is not None else get_access_token_expire_minutes()
    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=minutes)
    payload = {
        "sub": owner,
        "name": display_name,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
        "typ": "access",
    }
    body = _b64encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    signature = _b64encode(
        hmac.new(get_jwt_secret().encode("utf-8"), body.encode("ascii"), hashlib.sha256).digest()
    )
    token = f"{body}.{signature}"
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": minutes * 60,
        "expires_at": exp.isoformat(),
        "email": owner,
        "name": display_name,
    }


def decode_access_token(token: str) -> AuthenticatedUser:
    if not token or not isinstance(token, str):
        raise InvalidTokenError("Missing access token.")
    raw = token.strip()
    if raw.lower().startswith("bearer "):
        raw = raw[7:].strip()
    parts = raw.split(".")
    if len(parts) != 2:
        raise InvalidTokenError("Invalid access token.")
    body, signature = parts
    expected = _b64encode(
        hmac.new(get_jwt_secret().encode("utf-8"), body.encode("ascii"), hashlib.sha256).digest()
    )
    if not hmac.compare_digest(signature, expected):
        raise InvalidTokenError("Invalid or tampered access token.")
    try:
        payload = json.loads(_b64decode(body).decode("utf-8"))
    except Exception as exc:
        raise InvalidTokenError("Invalid access token payload.") from exc

    if payload.get("typ") != "access":
        raise InvalidTokenError("Invalid token type.")
    sub = payload.get("sub")
    exp = payload.get("exp")
    iat = payload.get("iat")
    if not sub or not isinstance(exp, int) or not isinstance(iat, int):
        raise InvalidTokenError("Invalid access token claims.")
    now_ts = int(datetime.now(timezone.utc).timestamp())
    if now_ts >= exp:
        raise InvalidTokenError("Access token has expired. Please sign in again.")
    try:
        email = normalize_email(str(sub))
    except ValueError as exc:
        raise InvalidTokenError("Invalid token subject.") from exc
    name = str(payload.get("name") or email.split("@")[0]).strip()
    return AuthenticatedUser(email=email, name=name, exp=exp, iat=iat)
