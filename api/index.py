"""
Vercel Python Function entrypoint for the existing FastAPI app.

The SPA owns `/`. API routes are served under `/api/*` (see root vercel.json)
and stripped here so backend routers stay `/auth`, `/documents`, etc.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


class StripApiPrefix:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") in {"http", "websocket"}:
            path = scope.get("path") or ""
            if path == "/api":
                scope = dict(scope, path="/")
            elif path.startswith("/api/"):
                stripped = path[4:]
                scope = dict(scope, path=stripped or "/")
        await self.app(scope, receive, send)


from app.main import app as fastapi_app  # noqa: E402

app = StripApiPrefix(fastapi_app)
handler = app
