import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import ValidationError

from app.database.mongodb import notes_collection, students_collection
from app.deps.auth import get_current_user, require_owned_email
from app.models.schemas import AskTutorRequest, TutorChatRequest, TutorChatResponse
from app.services.ai_service import generate_tutor_response
from app.services.auth_service import AuthenticatedUser
from app.services.rag_service import (
    chunk_document,
    extract_text_from_pdf,
    extract_text_from_txt,
    retrieve_relevant_passages,
)
from app.services.tutor_service import (
    TutorNotConfiguredError,
    TutorProviderError,
    TutorTimeoutError,
    answer_academic_question,
    get_tutor_status,
)

router = APIRouter(prefix="/ai", tags=["AI Tutor & Notes RAG"])

# Process-local cache only — not durable storage.
_notes_cache = {}


def _require_notes_mongo_for_write():
    if notes_collection is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "Notes storage is unavailable because MongoDB is not connected. "
                "In-memory notes persistence is disabled. Check /health/database."
            ),
        )


@router.post("/notes/upload")
async def upload_study_note(
    file: UploadFile = File(...),
    email: str = Form(...),
    subject: str = Form("General"),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Accepts PDF or text study notes, extracts text per page,
    segments into chunks with overlap, and indexes for retrieval.
    """
    owner = require_owned_email(email, current_user)
    _require_notes_mongo_for_write()

    filename = file.filename or "uploaded_note"
    extension = filename.split(".")[-1].lower()

    if extension not in ["pdf", "txt"]:
        raise HTTPException(
            status_code=400,
            detail="Unsupported format. Only PDF (.pdf) and plain text (.txt) files are supported.",
        )

    content_bytes = await file.read()
    if len(content_bytes) > 20 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (limit is 20MB)")

    try:
        if extension == "pdf":
            pages_data = extract_text_from_pdf(content_bytes)
        else:
            pages_data = extract_text_from_txt(content_bytes)

        if not pages_data:
            raise HTTPException(status_code=400, detail="Could not extract any readable text from file.")

        chunks = chunk_document(pages_data)
        note_id = str(uuid.uuid4())[:8]

        note_record = {
            "note_id": note_id,
            "email": owner,
            "filename": filename,
            "subject": subject,
            "total_pages": len(pages_data),
            "total_chunks": len(chunks),
            "chunks": chunks,
            "uploaded_at": datetime.utcnow().isoformat(),
        }

        _notes_cache[note_id] = note_record

        try:
            notes_collection.insert_one(note_record)
        except Exception as db_err:
            raise HTTPException(
                status_code=503,
                detail=(
                    "Could not save study note because MongoDB is unreachable. "
                    f"({type(db_err).__name__})."
                ),
            ) from db_err

        return {
            "message": f"Successfully processed '{filename}'",
            "note_id": note_id,
            "filename": filename,
            "subject": subject,
            "total_pages": len(pages_data),
            "total_chunks": len(chunks),
            "email": owner,
            "persistence": "mongo",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail="Failed to process study note.",
        ) from e


@router.get("/notes/{email}")
def get_student_notes(
    email: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Lists uploaded notes for the authenticated student."""
    owner = require_owned_email(email, current_user)
    notes_list = []
    if notes_collection is not None:
        try:
            records = list(notes_collection.find({"email": owner}, {"chunks": 0, "_id": 0}))
            if records:
                return {"notes": records, "email": owner}
        except Exception:
            pass

    for nid, n in _notes_cache.items():
        if n["email"] == owner:
            notes_list.append({
                "note_id": nid,
                "filename": n["filename"],
                "subject": n["subject"],
                "total_pages": n["total_pages"],
                "total_chunks": n["total_chunks"],
                "uploaded_at": n["uploaded_at"],
            })

    return {"notes": notes_list, "email": owner}


@router.get("/tutor/status")
def tutor_status_endpoint():
    """Reports whether the M14 general AI Tutor provider is configured."""
    return get_tutor_status()


@router.post("/tutor", response_model=TutorChatResponse)
def general_tutor_endpoint(
    request: TutorChatRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    M14 general academic AI Tutor.
    Answers student questions with a configured LLM provider.
    Does not use uploaded notes or fabricate note citations (M15–M16).
    Profile context is loaded only for the authenticated student.
    """
    question = (request.question or "").strip()
    if not question:
        raise HTTPException(status_code=422, detail="Question cannot be empty.")

    owner = require_owned_email(request.email, current_user)

    profile_context = None
    if request.include_profile_context and students_collection is not None:
        try:
            profile = students_collection.find_one(
                {"email": owner},
                {"_id": 0, "course": 1, "branch": 1, "year": 1, "subjects": 1},
            )
            if profile:
                profile_context = {
                    "course": profile.get("course"),
                    "branch": profile.get("branch"),
                    "year": profile.get("year"),
                    "subjects": profile.get("subjects"),
                }
        except Exception as profile_err:
            print(f"Non-fatal error loading profile context for tutor: {type(profile_err).__name__}")

    history = [m.model_dump() for m in request.conversation_history]

    try:
        result = answer_academic_question(
            question,
            subject=request.subject,
            conversation_history=history,
            profile_context=profile_context,
        )
        return result
    except TutorNotConfiguredError as cfg_err:
        raise HTTPException(status_code=503, detail=str(cfg_err)) from cfg_err
    except TutorTimeoutError as timeout_err:
        raise HTTPException(status_code=504, detail=str(timeout_err)) from timeout_err
    except TutorProviderError as provider_err:
        raise HTTPException(status_code=502, detail=str(provider_err)) from provider_err
    except ValueError as val_err:
        raise HTTPException(status_code=422, detail=str(val_err)) from val_err
    except ValidationError as validation_err:
        raise HTTPException(status_code=422, detail=str(validation_err)) from validation_err
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="AI Tutor failed unexpectedly. Please try again later.",
        ) from exc


@router.post("/ask")
def ask_tutor_endpoint(
    request: AskTutorRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Retrieves relevant passages from uploaded notes using TF-IDF cosine similarity,
    and returns a grounded answer with page citations.
    """
    owner = require_owned_email(request.email, current_user)
    all_chunks = []

    if request.note_id:
        note = None
        if request.note_id in _notes_cache:
            note = _notes_cache[request.note_id]
        elif notes_collection is not None:
            note = notes_collection.find_one({"note_id": request.note_id})
        if note:
            if (note.get("email") or "").lower() != owner:
                raise HTTPException(status_code=404, detail="Note not found.")
            all_chunks = note.get("chunks", [])
    else:
        if notes_collection is not None:
            notes = list(notes_collection.find({"email": owner}))
            for n in notes:
                all_chunks.extend(n.get("chunks", []))
        if not all_chunks:
            for n in _notes_cache.values():
                if n["email"] == owner:
                    all_chunks.extend(n.get("chunks", []))

    if not all_chunks:
        return {
            "answer": (
                "No uploaded study notes found for this inquiry. "
                "Please upload a PDF or text note first so the AI Tutor can assist you "
                "with your course materials."
            ),
            "grounded": False,
            "citations": [],
        }

    relevant_chunks = retrieve_relevant_passages(
        query=request.question,
        chunks=all_chunks,
        top_k=3,
        threshold=0.08,
    )

    tutor_reply = generate_tutor_response(
        question=request.question,
        retrieved_passages=relevant_chunks,
        student_subject=request.subject or "General",
    )

    return tutor_reply
