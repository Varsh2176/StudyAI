"""
Durable PDF / RAG blob storage using MongoDB GridFS (existing Atlas cluster).

Vercel serverless filesystems are ephemeral. When FILE_STORAGE_BACKEND=mongo
(or VERCEL=1), PDFs and TF-IDF indexes are stored in GridFS instead of local disk.
Local development keeps the existing disk paths unless mongo is forced.
"""

from __future__ import annotations

import os
from typing import Optional


class ObjectStorageError(Exception):
    def __init__(self, message: str, status_code: int = 503):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def storage_backend() -> str:
    raw = (os.getenv("FILE_STORAGE_BACKEND") or "").strip().lower()
    if raw in {"mongo", "mongodb", "gridfs"}:
        return "mongo"
    if raw in {"disk", "local", "filesystem"}:
        return "disk"
    if os.getenv("VERCEL"):
        return "mongo"
    return "disk"


def uses_mongo_blobs() -> bool:
    return storage_backend() == "mongo"


def _gridfs():
    from gridfs import GridFS

    from app.database.mongodb import db

    if db is None:
        raise ObjectStorageError(
            "Document storage is unavailable because MongoDB is not connected. "
            "Check /health/database.",
            status_code=503,
        )
    return GridFS(db, collection="studywise_fs")


def blob_filename(kind: str, email_key: str, document_id: str, name: str) -> str:
    return f"{kind}/{email_key}/{document_id}/{name}"


def put_blob(filename: str, data: bytes, content_type: str = "application/octet-stream") -> str:
    fs = _gridfs()
    delete_blob(filename)
    fs.put(data, filename=filename, contentType=content_type)
    return filename


def get_blob(filename: str) -> Optional[bytes]:
    fs = _gridfs()
    found = fs.find_one({"filename": filename})
    if found is None:
        return None
    return found.read()


def blob_exists(filename: str) -> bool:
    fs = _gridfs()
    return fs.find_one({"filename": filename}) is not None


def delete_blob(filename: str) -> bool:
    fs = _gridfs()
    deleted = False
    for item in fs.find({"filename": filename}):
        fs.delete(item._id)
        deleted = True
    return deleted


def delete_prefix(prefix: str) -> bool:
    fs = _gridfs()
    deleted = False
    for item in fs.find({"filename": {"$regex": f"^{prefix}"}}):
        fs.delete(item._id)
        deleted = True
    return deleted
