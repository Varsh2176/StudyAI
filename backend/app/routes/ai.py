import uuid
from datetime import datetime
from pydantic import ValidationError
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from app.models.schemas import AskTutorRequest, TutorChatRequest, TutorChatResponse
from app.services.rag_service import (
    extract_text_from_pdf,
    extract_text_from_txt,
    chunk_document,
    retrieve_relevant_passages
)
from app.services.ai_service import generate_tutor_response
from app.services.tutor_service import (
    answer_academic_question,
    get_tutor_status,
    TutorNotConfiguredError,
    TutorTimeoutError,
    TutorProviderError,
)
from app.database.mongodb import notes_collection, students_collection

router = APIRouter(prefix="/ai", tags=["AI Tutor & Notes RAG"])

# In-memory storage for notes if MongoDB is disconnected
_notes_cache = {}


@router.post("/notes/upload")
async def upload_study_note(
    file: UploadFile = File(...),
    email: str = Form("student@studywise.ai"),
    subject: str = Form("General")
):
    """
    Accepts PDF or text study notes, extracts text per page,
    segments into chunks with overlap, and indexes for retrieval.
    """
    filename = file.filename or "uploaded_note"
    extension = filename.split(".")[-1].lower()

    if extension not in ["pdf", "txt"]:
        raise HTTPException(
            status_code=400,
            detail="Unsupported format. Only PDF (.pdf) and plain text (.txt) files are supported."
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
            "email": email,
            "filename": filename,
            "subject": subject,
            "total_pages": len(pages_data),
            "total_chunks": len(chunks),
            "chunks": chunks,
            "uploaded_at": datetime.utcnow().isoformat()
        }

        # Cache in memory
        _notes_cache[note_id] = note_record

        # Store in MongoDB
        if notes_collection is not None:
            try:
                notes_collection.insert_one(note_record)
            except Exception as db_err:
                print(f"Non-fatal error saving note to MongoDB: {db_err}")

        return {
            "message": f"Successfully processed '{filename}'",
            "note_id": note_id,
            "filename": filename,
            "subject": subject,
            "total_pages": len(pages_data),
            "total_chunks": len(chunks)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process study note: {str(e)}")


@router.get("/notes/{email}")
def get_student_notes(email: str):
    """Lists uploaded notes for a student."""
    notes_list = []
    if notes_collection is not None:
        try:
            records = list(notes_collection.find({"email": email}, {"chunks": 0, "_id": 0}))
            if records:
                return {"notes": records}
        except Exception:
            pass

    # Fallback to in-memory cache
    for nid, n in _notes_cache.items():
        if n["email"] == email:
            notes_list.append({
                "note_id": nid,
                "filename": n["filename"],
                "subject": n["subject"],
                "total_pages": n["total_pages"],
                "total_chunks": n["total_chunks"],
                "uploaded_at": n["uploaded_at"]
            })

    return {"notes": notes_list}


@router.get("/tutor/status")
def tutor_status_endpoint():
    """Reports whether the M14 general AI Tutor provider is configured."""
    return get_tutor_status()


@router.post("/tutor", response_model=TutorChatResponse)
def general_tutor_endpoint(request: TutorChatRequest):
    """
    M14 general academic AI Tutor.
    Answers student questions with a configured LLM provider.
    Does not use uploaded notes or fabricate note citations (M15–M16).
    """
    question = (request.question or "").strip()
    if not question:
        raise HTTPException(status_code=422, detail="Question cannot be empty.")

    profile_context = None
    if request.include_profile_context and request.email and students_collection is not None:
        try:
            profile = students_collection.find_one(
                {"email": request.email},
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
            # Non-fatal: tutor still works without profile enrichment.
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
def ask_tutor_endpoint(request: AskTutorRequest):
    """
    Retrieves relevant passages from uploaded notes using TF-IDF cosine similarity,
    and returns a grounded answer with page citations.
    """
    all_chunks = []

    # Check MongoDB or memory cache for student's notes
    if request.note_id:
        if request.note_id in _notes_cache:
            all_chunks = _notes_cache[request.note_id].get("chunks", [])
        elif notes_collection is not None:
            note = notes_collection.find_one({"note_id": request.note_id})
            if note:
                all_chunks = note.get("chunks", [])
    elif request.email:
        # Collect chunks across student's notes
        if notes_collection is not None:
            notes = list(notes_collection.find({"email": request.email}))
            for n in notes:
                all_chunks.extend(n.get("chunks", []))
        if not all_chunks:
            for n in _notes_cache.values():
                if n["email"] == request.email:
                    all_chunks.extend(n.get("chunks", []))

    if not all_chunks:
        return {
            "answer": "No uploaded study notes found for this inquiry. Please upload a PDF or text note first so the AI Tutor can assist you with your course materials.",
            "grounded": False,
            "citations": []
        }

    relevant_chunks = retrieve_relevant_passages(
        query=request.question,
        chunks=all_chunks,
        top_k=3,
        threshold=0.08
    )

    tutor_reply = generate_tutor_response(
        question=request.question,
        retrieved_passages=relevant_chunks,
        student_subject=request.subject or "General"
    )

    return tutor_reply
