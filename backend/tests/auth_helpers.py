"""Helpers for M10 auth/ownership tests (no secrets printed)."""

from __future__ import annotations

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
