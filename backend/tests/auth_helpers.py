"""Helpers for M10/M11 auth/ownership tests (no secrets printed)."""

from __future__ import annotations

from starlette.requests import Request

from app.services.auth_service import AuthenticatedUser, create_access_token, hash_password


def auth_user(email: str = "alice@example.edu", name: str = "Alice") -> AuthenticatedUser:
    return AuthenticatedUser(
        email=email.strip().lower(),
        name=name,
        exp=4_000_000_000,
        iat=1_700_000_000,
    )


def mint_token(email: str = "alice@example.edu", name: str = "Alice", minutes: int = 60) -> str:
    return create_access_token(email=email, name=name, expires_minutes=minutes)["access_token"]


def hashed(password: str = "password123") -> str:
    return hash_password(password)


def fake_request(client_host: str = "127.0.0.1") -> Request:
    """Minimal ASGI Request for calling auth route functions in unit tests."""
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/auth/test",
        "raw_path": b"/auth/test",
        "query_string": b"",
        "headers": [],
        "client": (client_host, 12345),
        "server": ("testserver", 80),
    }
    return Request(scope)


class FakeUsersCollection:
    def __init__(self):
        self.rows = {}

    def find_one(self, query, projection=None):
        email = (query or {}).get("email")
        row = self.rows.get(email)
        if not row:
            return None
        if projection:
            return {k: v for k, v in row.items() if k in projection or k == "email"}
        return dict(row)

    def insert_one(self, doc):
        email = doc["email"]
        if email in self.rows:
            raise ValueError("duplicate")
        self.rows[email] = dict(doc)
        return type("InsertResult", (), {"inserted_id": email})()


class FakeStudyPlansCollection:
    def __init__(self):
        self.rows = {}

    def update_one(self, filt, update, upsert=False):
        email = (filt or {}).get("email")
        patch = (update or {}).get("$set") or {}
        if email is None:
            return
        existing = self.rows.get(email)
        if existing is None and upsert:
            self.rows[email] = dict(patch)
            return
        if existing is not None:
            existing.update(patch)

    def find_one(self, filt, projection=None, sort=None):
        email = (filt or {}).get("email")
        row = self.rows.get(email)
        if not row:
            return None
        data = dict(row)
        if projection:
            include = {k for k, v in projection.items() if v}
            exclude = {k for k, v in projection.items() if not v}
            if include:
                data = {k: v for k, v in data.items() if k in include or k == "email"}
            for k in exclude:
                data.pop(k, None)
        return data


class FakeDocumentsCollection:
    def __init__(self):
        self.rows = {}

    def update_one(self, filt, update, upsert=False):
        doc_id = (filt or {}).get("document_id")
        patch = (update or {}).get("$set") or {}
        existing = self.rows.get(doc_id)
        if existing is None and upsert:
            self.rows[doc_id] = dict(patch)
            return
        if existing is not None:
            existing.update(patch)

    def find_one(self, filt, projection=None):
        doc_id = (filt or {}).get("document_id")
        email = (filt or {}).get("email")
        row = None
        if doc_id:
            row = self.rows.get(doc_id)
        elif email:
            for candidate in self.rows.values():
                if candidate.get("email") == email:
                    row = candidate
                    break
        if not row:
            return None
        data = dict(row)
        if projection:
            include = {k for k, v in projection.items() if v}
            exclude = {k for k, v in projection.items() if not v}
            if include:
                data = {k: v for k, v in data.items() if k in include or k == "document_id"}
            for k in exclude:
                data.pop(k, None)
        return data

    def find(self, filt, projection=None):
        email = (filt or {}).get("email")
        rows = [dict(r) for r in self.rows.values() if not email or r.get("email") == email]

        class _Cursor(list):
            def sort(self, *args, **kwargs):
                return self

        return _Cursor(rows)

    def delete_one(self, filt):
        doc_id = (filt or {}).get("document_id")
        email = (filt or {}).get("email")
        row = self.rows.get(doc_id)
        deleted = 0
        if row and (not email or row.get("email") == email):
            del self.rows[doc_id]
            deleted = 1
        return type("DeleteResult", (), {"deleted_count": deleted})()
