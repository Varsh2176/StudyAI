"""
M15 — Secure PDF upload, local file storage, and text extraction.

Stores PDF bytes on disk (not in MongoDB). Metadata + extracted page text
are persisted for future M16 retrieval. No RAG/chunking/embeddings here.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from pypdf import PdfReader
from pypdf.errors import PdfReadError


PDF_MAGIC = b"%PDF"
DEFAULT_MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB
DEFAULT_MAX_EXTRACTED_CHARS = 500_000
DEFAULT_MAX_PAGES = 200


class PdfDocumentError(Exception):
    """Base PDF document error with HTTP-friendly attributes."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def get_max_upload_bytes() -> int:
    raw = os.getenv("PDF_UPLOAD_MAX_BYTES", str(DEFAULT_MAX_UPLOAD_BYTES))
    try:
        value = int(raw)
        return max(1024, min(value, 50 * 1024 * 1024))
    except (TypeError, ValueError):
        return DEFAULT_MAX_UPLOAD_BYTES


def get_max_extracted_chars() -> int:
    raw = os.getenv("PDF_MAX_EXTRACTED_CHARS", str(DEFAULT_MAX_EXTRACTED_CHARS))
    try:
        value = int(raw)
        return max(1000, min(value, 2_000_000))
    except (TypeError, ValueError):
        return DEFAULT_MAX_EXTRACTED_CHARS


def get_storage_root() -> Path:
    configured = os.getenv("PDF_STORAGE_DIR", "storage/documents").strip() or "storage/documents"
    root = Path(configured)
    if not root.is_absolute():
        # Resolve relative to backend/ working directory
        root = Path.cwd() / root
    root.mkdir(parents=True, exist_ok=True)
    return root.resolve()


def sanitize_original_filename(filename: Optional[str]) -> str:
    name = (filename or "document.pdf").replace("\\", "/").split("/")[-1]
    name = re.sub(r"[^\w.\- ()\[\]]+", "_", name).strip(" .")
    if not name.lower().endswith(".pdf"):
        name = f"{name}.pdf" if name else "document.pdf"
    if len(name) > 180:
        stem = name[:-4][:170]
        name = f"{stem}.pdf"
    return name or "document.pdf"


def owner_storage_key(email: str) -> str:
    digest = hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()[:24]
    return digest


def require_student_email(email: Optional[str]) -> str:
    cleaned = (email or "").strip().lower()
    if not cleaned or "@" not in cleaned:
        raise PdfDocumentError(
            "Student email is required to upload or manage study documents.",
            status_code=401,
        )
    if len(cleaned) > 254 or any(ch in cleaned for ch in ("/", "\\", "..")):
        raise PdfDocumentError("Invalid student email.", status_code=400)
    return cleaned


def validate_pdf_bytes(file_bytes: bytes, declared_content_type: Optional[str] = None) -> None:
    if not file_bytes:
        raise PdfDocumentError("Uploaded file is empty.", status_code=400)

    max_bytes = get_max_upload_bytes()
    if len(file_bytes) > max_bytes:
        raise PdfDocumentError(
            f"File exceeds the maximum upload size of {max_bytes // (1024 * 1024)} MB.",
            status_code=413,
        )

    # Do not trust extension/MIME alone — require PDF signature at byte 0.
    if not file_bytes.startswith(PDF_MAGIC):
        raise PdfDocumentError(
            "Invalid file signature. Only PDF documents are accepted.",
            status_code=400,
        )

    content_type = (declared_content_type or "").split(";")[0].strip().lower()
    if content_type and content_type not in {
        "application/pdf",
        "application/x-pdf",
        "binary/octet-stream",
        "application/octet-stream",
    }:
        # Soft signal only when browser sends an obviously wrong type with a PDF signature.
        # Still require parse validation below.
        pass

    try:
        reader = PdfReader(io.BytesIO(file_bytes), strict=False)
        # Force parse of page tree
        _ = len(reader.pages)
        if getattr(reader, "is_encrypted", False):
            try:
                # Empty password attempt; encrypted PDFs without open access are rejected.
                if reader.decrypt("") == 0 and reader.is_encrypted:
                    raise PdfDocumentError(
                        "Encrypted PDFs are not supported. Please upload an unencrypted PDF.",
                        status_code=400,
                    )
            except PdfDocumentError:
                raise
            except Exception as exc:
                raise PdfDocumentError(
                    "Unable to open encrypted PDF. Please upload an unencrypted PDF.",
                    status_code=400,
                ) from exc
    except PdfDocumentError:
        raise
    except PdfReadError as exc:
        raise PdfDocumentError(
            "The uploaded file is not a valid PDF or appears corrupted.",
            status_code=400,
        ) from exc
    except Exception as exc:
        raise PdfDocumentError(
            "The uploaded file could not be parsed as a PDF.",
            status_code=400,
        ) from exc


def extract_pdf_text(file_bytes: bytes) -> Dict[str, Any]:
    """
    Extract readable text per page. Does not perform OCR.
    """
    max_chars = get_max_extracted_chars()
    max_pages = int(os.getenv("PDF_MAX_PAGES", str(DEFAULT_MAX_PAGES)))
    max_pages = max(1, min(max_pages, 500))

    try:
        reader = PdfReader(io.BytesIO(file_bytes), strict=False)
        page_count = len(reader.pages)
    except Exception as exc:
        raise PdfDocumentError(
            "Text extraction failed because the PDF could not be read.",
            status_code=400,
        ) from exc

    if page_count == 0:
        raise PdfDocumentError("PDF contains no pages.", status_code=400)
    if page_count > max_pages:
        raise PdfDocumentError(
            f"PDF has too many pages (limit is {max_pages}).",
            status_code=400,
        )

    pages: List[Dict[str, Any]] = []
    total_chars = 0
    truncated = False

    for idx, page in enumerate(reader.pages):
        try:
            raw = page.extract_text() or ""
        except Exception:
            raw = ""
        text = re.sub(r"[ \t]+", " ", raw)
        text = re.sub(r"\n{3,}", "\n\n", text).strip()

        remaining = max_chars - total_chars
        if remaining <= 0:
            truncated = True
            break
        if len(text) > remaining:
            text = text[:remaining]
            truncated = True

        pages.append({"page": idx + 1, "text": text, "char_count": len(text)})
        total_chars += len(text)
        if truncated:
            break

    # Include empty pages in page_count from PDF, but pages list may omit trailing unprocessed pages if truncated.
    extracted_characters = sum(p["char_count"] for p in pages)
    text_available = extracted_characters > 0
    ocr_required = not text_available

    if ocr_required:
        status = "processed_no_text"
        message = (
            "PDF was stored successfully, but no extractable text was found. "
            "This often means the file is scanned/image-based. OCR is not enabled in M15."
        )
    else:
        status = "processed"
        message = "PDF stored and text extracted successfully."
        if truncated:
            message += " Extracted text was truncated to the configured size limit."

    return {
        "status": status,
        "page_count": page_count,
        "extracted_characters": extracted_characters,
        "text_available": text_available,
        "ocr_required": ocr_required,
        "extraction_message": message,
        "pages": pages,
        "extraction_truncated": truncated,
    }


def _document_paths(email: str, document_id: str) -> Tuple[Path, Path]:
    # Prevent path traversal: document_id must be a plain UUID-like token.
    if not re.fullmatch(r"[A-Za-z0-9\-]{8,64}", document_id):
        raise PdfDocumentError("Invalid document identifier.", status_code=400)

    storage_root = get_storage_root()
    owner_dir = (storage_root / owner_storage_key(email)).resolve()
    if storage_root not in owner_dir.parents and owner_dir != storage_root:
        raise PdfDocumentError("Invalid storage path.", status_code=400)
    owner_dir.mkdir(parents=True, exist_ok=True)

    pdf_path = (owner_dir / f"{document_id}.pdf").resolve()
    meta_sidecar = (owner_dir / f"{document_id}.meta.json").resolve()
    if storage_root not in pdf_path.parents:
        raise PdfDocumentError("Invalid storage path.", status_code=400)
    return pdf_path, meta_sidecar


def save_pdf_bytes(email: str, document_id: str, file_bytes: bytes) -> str:
    pdf_path, _ = _document_paths(email, document_id)
    pdf_path.write_bytes(file_bytes)
    # Return storage key relative to storage root (never absolute path in APIs)
    return f"{owner_storage_key(email)}/{document_id}.pdf"


def write_sidecar_metadata(email: str, document_id: str, record: Dict[str, Any]) -> None:
    _, sidecar = _document_paths(email, document_id)
    safe = {k: v for k, v in record.items() if k != "_id"}
    sidecar.write_text(json.dumps(safe, ensure_ascii=False), encoding="utf-8")


def delete_stored_files(email: str, document_id: str) -> Dict[str, bool]:
    pdf_path, sidecar = _document_paths(email, document_id)
    result = {"pdf_deleted": False, "sidecar_deleted": False}
    try:
        if pdf_path.exists():
            pdf_path.unlink()
            result["pdf_deleted"] = True
    except OSError:
        pass
    try:
        if sidecar.exists():
            sidecar.unlink()
            result["sidecar_deleted"] = True
    except OSError:
        pass
    return result


def build_document_record(
    *,
    email: str,
    original_filename: str,
    file_bytes: bytes,
    subject: Optional[str] = None,
    content_type: Optional[str] = None,
) -> Dict[str, Any]:
    validate_pdf_bytes(file_bytes, declared_content_type=content_type)
    document_id = str(uuid.uuid4())
    safe_name = sanitize_original_filename(original_filename)
    extraction = extract_pdf_text(file_bytes)
    storage_key = save_pdf_bytes(email, document_id, file_bytes)
    now = datetime.now(timezone.utc).isoformat()

    record = {
        "document_id": document_id,
        "email": email,
        "filename": safe_name,
        "original_filename": safe_name,
        "subject": (subject or "General").strip()[:120] or "General",
        "content_type": "application/pdf",
        "file_size_bytes": len(file_bytes),
        "status": extraction["status"],
        "page_count": extraction["page_count"],
        "extracted_characters": extraction["extracted_characters"],
        "text_available": extraction["text_available"],
        "ocr_required": extraction["ocr_required"],
        "extraction_message": extraction["extraction_message"],
        "extraction_truncated": extraction["extraction_truncated"],
        "pages": extraction["pages"],
        "storage_key": storage_key,
        "uploaded_at": now,
        "updated_at": now,
    }
    write_sidecar_metadata(email, document_id, record)
    return record


def public_document_summary(record: Dict[str, Any]) -> Dict[str, Any]:
    """API-safe metadata without filesystem paths or full page text."""
    return {
        "document_id": record.get("document_id"),
        "filename": record.get("filename") or record.get("original_filename"),
        "subject": record.get("subject"),
        "status": record.get("status"),
        "file_size_bytes": record.get("file_size_bytes"),
        "page_count": record.get("page_count"),
        "extracted_characters": record.get("extracted_characters"),
        "text_available": bool(record.get("text_available")),
        "ocr_required": bool(record.get("ocr_required")),
        "extraction_message": record.get("extraction_message"),
        "uploaded_at": record.get("uploaded_at"),
        "updated_at": record.get("updated_at"),
        "rag_status": record.get("rag_status") or "not_indexed",
        "rag_chunk_count": record.get("rag_chunk_count") or 0,
        "rag_indexed_at": record.get("rag_indexed_at"),
    }


def public_upload_response(record: Dict[str, Any]) -> Dict[str, Any]:
    summary = public_document_summary(record)
    summary["message"] = record.get("extraction_message")
    return summary


def public_text_payload(record: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "document_id": record.get("document_id"),
        "filename": record.get("filename"),
        "status": record.get("status"),
        "page_count": record.get("page_count"),
        "extracted_characters": record.get("extracted_characters"),
        "text_available": bool(record.get("text_available")),
        "ocr_required": bool(record.get("ocr_required")),
        "pages": record.get("pages") or [],
    }
