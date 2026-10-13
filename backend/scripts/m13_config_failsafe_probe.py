"""Probe production fail-safe config behavior without printing secrets or touching .env."""
from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)


def main() -> int:
    from app.main import get_cors_origins
    from app.services.auth_service import AuthConfigError, get_jwt_secret

    failed = 0

    try:
        with patch.dict(
            os.environ,
            {"APP_ENV": "production", "JWT_SECRET": "replace_with_a_long_random_secret"},
            clear=False,
        ):
            get_jwt_secret()
        print("[FAIL] weak JWT accepted in production")
        failed += 1
    except AuthConfigError:
        print("[PASS] production rejects weak JWT_SECRET")

    with patch.dict(os.environ, {"APP_ENV": "production", "CORS_ORIGINS": ""}, clear=False):
        origins = get_cors_origins()
        if origins == []:
            print("[PASS] production empty CORS_ORIGINS fail-closed")
        else:
            print(f"[FAIL] expected [] got {origins}")
            failed += 1

    example = (ROOT / ".env.example").read_text(encoding="utf-8")
    for name in (
        "MONGODB_URI",
        "DATABASE_NAME",
        "JWT_SECRET",
        "APP_ENV",
        "CORS_ORIGINS",
        "GEMINI_API_KEY",
    ):
        ok = name in example
        print(f"[{'PASS' if ok else 'FAIL'}] .env.example documents {name}")
        failed += 0 if ok else 1

    fe = (ROOT.parent / "frontend" / ".env.example").read_text(encoding="utf-8")
    ok = "VITE_API_BASE_URL" in fe
    print(f"[{'PASS' if ok else 'FAIL'}] frontend/.env.example documents VITE_API_BASE_URL")
    failed += 0 if ok else 1

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
