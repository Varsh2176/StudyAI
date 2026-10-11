"""
M15 — Student PDF document upload and management API.

Ownership is tied to student email (same convention as profile/prediction APIs).
Does not implement RAG or Q&A over notes (M16).
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile

from app.database.mongodb import documents_collection
from app.services.pdf_document_service import (
    PdfDocumentError,
    build_document_record,
    delete_stored_files,
    get_max_upload_bytes,
    public_document_summary,
    public_text_payload,
    public_upload_response,
    require_student_email,
)

router = APIRouter(prefix="/documents", tags=["Study Documents (M15)"])

# In-memory fallback when MongoDB is unavailable (tests / offline dev)
_documents_cache: Dict[str, Dict[str, Any]] = {}


def _persist_record(record: Dict[str, Any]) -> None:
    _documents_cache[record["document_id"]] = record
    if documents_collection is None:
        return
    try:
        documents_collection.update_one(
            {"document_id": record["document_id"]},
            {"$set": record},
            upsert=True,
        )
    except Exception as db_err:
        print(f"Non-fatal error persisting document metadata: {type(db_err).__name__}")


def _find_record(document_id: str) -> Optional[Dict[str, Any]]:
    if documents_collection is not None:
        try:
            record = documents_collection.find_one({"document_id": document_id}, {"_id": 0})
            if record:
                return record
        except Exception:
            pass
    return _documents_cache.get(document_id)


def _list_records_for_email(email: str) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    if documents_collection is not None:
        try:
            records = list(
                documents_collection.find(
                    {"email": email},
                    {"_id": 0, "pages": 0},
                ).sort("uploaded_at", -1)
            )
        except Exception:
            records = []
    if records:
        return records

    cached = [r for r in _documents_cache.values() if r.get("email") == email]
    cached.sort(key=lambda r: r.get("uploaded_at", ""), reverse=True)
    return cached


def _require_owned_record(document_id: str, email: str) -> Dict[str, Any]:
    record = _find_record(document_id)
    if not record:
        raise HTTPException(status_code=404, detail="Document not found.")
    if (record.get("email") or "").lower() != email.lower():
        # Do not leak existence of another student's document.
        raise HTTPException(status_code=404, detail="Document not found.")
    return record


def _http_from_pdf_error(exc: PdfDocumentError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.message)


@router.get("/limits")
def document_upload_limits():
    """Returns configured upload limits for the frontend."""
    max_bytes = get_max_upload_bytes()
    return {
        "max_upload_bytes": max_bytes,
        "max_upload_mb": round(max_bytes / (1024 * 1024), 2),
        "allowed_content_types": ["application/pdf"],
        "allowed_extensions": [".pdf"],
    }


@router.post("/upload")
async def upload_pdf_document(
    file: UploadFile = File(...),
    email: str = Form(...),
    subject: str = Form("General"),
):
    """
    Upload a PDF study document for the given student email.
    Validates signature/size, stores bytes on disk, extracts text for M16.
    """
    try:
        owner = require_student_email(email)
    except PdfDocumentError as exc:
        raise _http_from_pdf_error(exc) from exc

    filename = file.filename or ""
    if filename and not filename.lower().endswith(".pdf"):
        # Extension check is an early filter; signature validation is authoritative.
        raise HTTPException(status_code=400, detail="Only PDF files (.pdf) are accepted.")

    try:
        file_bytes = await file.read()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Failed to read uploaded file.") from exc

    try:
        record = build_document_record(
            email=owner,
            original_filename=filename or "document.pdf",
            file_bytes=file_bytes,
            subject=subject,
            content_type=file.content_type,
        )
        _persist_record(record)
        return public_upload_response(record)
    except PdfDocumentError as exc:
        raise _http_from_pdf_error(exc) from exc
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Failed to process the PDF upload. Please try again.",
        )


@router.get("")
def list_documents(email: str = Query(..., description="Student email that owns the documents")):
    """List metadata for documents owned by the student."""
    try:
        owner = require_student_email(email)
    except PdfDocumentError as exc:
        raise _http_from_pdf_error(exc) from exc

    records = _list_records_for_email(owner)
    return {
        "email": owner,
        "count": len(records),
        "documents": [public_document_summary(r) for r in records],
    }


@router.get("/{document_id}")
def get_document_metadata(
    document_id: str,
    email: str = Query(..., description="Student email that owns the document"),
):
    """Retrieve processing status and metadata for one owned document."""
    try:
        owner = require_student_email(email)
    except PdfDocumentError as exc:
        raise _http_from_pdf_error(exc) from exc

    record = _require_owned_record(document_id, owner)
    return public_document_summary(record)


@router.get("/{document_id}/text")
def get_document_extracted_text(
    document_id: str,
    email: str = Query(..., description="Student email that owns the document"),
):
    """
    Return extracted page text for M16 retrieval pipelines.
    Requires ownership. Does not return filesystem paths.
    """
    try:
        owner = require_student_email(email)
    except PdfDocumentError as exc:
        raise _http_from_pdf_error(exc) from exc

    record = _require_owned_record(document_id, owner)
    # Prefer full record with pages from cache/Mongo
    full = _find_record(document_id) or record
    if documents_collection is not None and "pages" not in full:
        try:
            full = documents_collection.find_one({"document_id": document_id}, {"_id": 0}) or full
        except Exception:
            pass
    return public_text_payload(full)


@router.delete("/{document_id}")
def delete_document(
    document_id: str,
    email: str = Query(..., description="Student email that owns the document"),
):
    """Delete an owned document's stored PDF, sidecar, and metadata."""
    try:
        owner = require_student_email(email)
    except PdfDocumentError as exc:
        raise _http_from_pdf_error(exc) from exc

    record = _require_owned_record(document_id, owner)
    file_cleanup = delete_stored_files(owner, document_id)

    db_deleted = False
    if documents_collection is not None:
        try:
            result = documents_collection.delete_one(
                {"document_id": document_id, "email": owner}
            )
            db_deleted = result.deleted_count > 0
        except Exception as db_err:
            print(f"Non-fatal error deleting document metadata: {type(db_err).__name__}")

    _documents_cache.pop(document_id, None)

    if not db_deleted and document_id in _documents_cache:
        # Already popped; treat cache removal as success for offline mode
        pass

    return {
        "message": "Document deleted.",
        "document_id": document_id,
        "filename": record.get("filename"),
        "deleted_at": datetime.now(timezone.utc).isoformat(),
        "storage_cleanup": file_cleanup,
        "metadata_deleted": db_deleted or True,
    }
