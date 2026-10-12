"""
M15/M16 — Student PDF document upload, text extraction, and RAG indexing/Q&A.

Ownership is tied to student email (same convention as profile/prediction APIs).
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, File, Form, HTTPException, Query, UploadFile

from app.database.mongodb import documents_collection
from app.models.schemas import RagAskRequest, RagAskResponse
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
from app.services.document_rag_service import (
    DocumentRagError,
    delete_document_index,
    generate_rag_answer,
    get_index_status,
    index_document_record,
    retrieve_from_document,
    retrieve_from_owned_documents,
)

router = APIRouter(prefix="/documents", tags=["Study Documents (M15/M16)"])

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


def _http_from_rag_error(exc: DocumentRagError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.message)


def _update_rag_metadata(document_id: str, email: str, index_info: Dict[str, Any]) -> None:
    patch = {
        "rag_status": index_info.get("status"),
        "rag_chunk_count": index_info.get("chunk_count", 0),
        "rag_indexed_at": index_info.get("indexed_at"),
        "rag_embedding_provider": index_info.get("embedding_provider"),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    cached = _documents_cache.get(document_id)
    if cached and (cached.get("email") or "").lower() == email.lower():
        cached.update(patch)
        _documents_cache[document_id] = cached
    if documents_collection is not None:
        try:
            documents_collection.update_one(
                {"document_id": document_id, "email": email},
                {"$set": patch},
            )
        except Exception as db_err:
            print(f"Non-fatal error updating RAG metadata: {type(db_err).__name__}")


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


@router.post("/rag/ask", response_model=RagAskResponse)
def ask_documents_rag(request: RagAskRequest = Body(...)):
    """
    M16: Ask a question over one owned document or all indexed owned documents.
    Answers are grounded in retrieved chunks; citations include filename + page.
    """
    try:
        owner = require_student_email(request.email)
    except PdfDocumentError as exc:
        raise _http_from_pdf_error(exc) from exc

    top_k = request.top_k
    document_scope = "single_document" if request.document_id else "all_owned_indexed"

    try:
        if request.document_id:
            _require_owned_record(request.document_id, owner)
            status = get_index_status(owner, request.document_id)
            if status.get("status") != "indexed":
                raise DocumentRagError(
                    "Document is not indexed for RAG. Open Materials and click Index, or re-upload.",
                    status_code=409,
                )
            retrieved = retrieve_from_document(
                email=owner,
                document_id=request.document_id,
                question=request.question,
                top_k=top_k,
            )
        else:
            owned = _list_records_for_email(owner)
            indexed_ids = []
            for doc in owned:
                doc_id = doc.get("document_id")
                if not doc_id:
                    continue
                if get_index_status(owner, doc_id).get("status") == "indexed":
                    indexed_ids.append(doc_id)
            if not indexed_ids:
                raise DocumentRagError(
                    "No indexed study documents found for this student. Upload a PDF and index it first.",
                    status_code=409,
                )
            retrieved = retrieve_from_owned_documents(
                email=owner,
                document_ids=indexed_ids,
                question=request.question,
                top_k=top_k,
            )
    except DocumentRagError as exc:
        raise _http_from_rag_error(exc) from exc

    result = generate_rag_answer(question=request.question, retrieved=retrieved)
    return {
        "answer": result["answer"],
        "grounded": result["grounded"],
        "mode": result["mode"],
        "sources": result["sources"],
        "provider": result.get("provider"),
        "model_used": result.get("model_used"),
        "retrieved_count": len(retrieved),
        "document_scope": document_scope,
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
        # Best-effort auto-index for RAG when extractable text exists.
        if record.get("text_available"):
            try:
                index_info = index_document_record(record, force=False)
                record["rag_status"] = index_info.get("status")
                record["rag_chunk_count"] = index_info.get("chunk_count", 0)
                record["rag_indexed_at"] = index_info.get("indexed_at")
                record["rag_embedding_provider"] = index_info.get("embedding_provider")
            except DocumentRagError as rag_err:
                record["rag_status"] = "index_failed"
                record["rag_error"] = rag_err.message
        else:
            record["rag_status"] = "not_indexable"

        _persist_record(record)
        response = public_upload_response(record)
        response["rag_status"] = record.get("rag_status")
        response["rag_chunk_count"] = record.get("rag_chunk_count", 0)
        return response
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
    documents = []
    for record in records:
        summary = public_document_summary(record)
        doc_id = summary.get("document_id")
        if doc_id:
            try:
                status = get_index_status(owner, doc_id)
                summary["rag_status"] = status.get("status") or summary.get("rag_status")
                summary["rag_chunk_count"] = status.get("chunk_count") or summary.get("rag_chunk_count") or 0
                summary["rag_indexed_at"] = status.get("indexed_at") or summary.get("rag_indexed_at")
            except Exception:
                pass
        documents.append(summary)
    return {
        "email": owner,
        "count": len(documents),
        "documents": documents,
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


@router.post("/{document_id}/index")
def index_document_for_rag(
    document_id: str,
    email: str = Query(..., description="Student email that owns the document"),
    force: bool = Query(False, description="Rebuild index even if content hash matches"),
):
    """M16: Chunk + embed an owned document into the persistent local RAG index."""
    try:
        owner = require_student_email(email)
    except PdfDocumentError as exc:
        raise _http_from_pdf_error(exc) from exc

    record = _require_owned_record(document_id, owner)
    full = _find_record(document_id) or record
    if "pages" not in full and documents_collection is not None:
        try:
            full = documents_collection.find_one({"document_id": document_id}, {"_id": 0}) or full
        except Exception:
            pass

    try:
        index_info = index_document_record(full, force=force)
        _update_rag_metadata(document_id, owner, index_info)
        return index_info
    except DocumentRagError as exc:
        raise _http_from_rag_error(exc) from exc


@router.get("/{document_id}/index-status")
def document_rag_index_status(
    document_id: str,
    email: str = Query(..., description="Student email that owns the document"),
):
    """M16: Return RAG indexing status for an owned document."""
    try:
        owner = require_student_email(email)
    except PdfDocumentError as exc:
        raise _http_from_pdf_error(exc) from exc

    _require_owned_record(document_id, owner)
    return get_index_status(owner, document_id)


@router.delete("/{document_id}")
def delete_document(
    document_id: str,
    email: str = Query(..., description="Student email that owns the document"),
):
    """Delete an owned document's stored PDF, sidecar, RAG index, and metadata."""
    try:
        owner = require_student_email(email)
    except PdfDocumentError as exc:
        raise _http_from_pdf_error(exc) from exc

    record = _require_owned_record(document_id, owner)
    file_cleanup = delete_stored_files(owner, document_id)
    rag_deleted = delete_document_index(owner, document_id)

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

    return {
        "message": "Document deleted.",
        "document_id": document_id,
        "filename": record.get("filename"),
        "deleted_at": datetime.now(timezone.utc).isoformat(),
        "storage_cleanup": file_cleanup,
        "rag_index_deleted": rag_deleted,
        "metadata_deleted": db_deleted or True,
    }
