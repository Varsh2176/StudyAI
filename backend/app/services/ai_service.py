import os
import json
import urllib.request
import urllib.error
from typing import List, Dict, Any


def generate_tutor_response(
    question: str,
    retrieved_passages: List[Dict[str, Any]],
    student_subject: str = "General"
) -> Dict[str, Any]:
    """
    Modular AI Tutor grounded answer generator.
    Strictly grounds answers in retrieved study note material with page citations.
    Explains when information is absent from notes.
    Works independently even if LLM API is unavailable.
    """
    if not retrieved_passages:
        return {
            "answer": "This information is not available in your uploaded study notes. Please check if your notes cover this topic or try asking with specific terms from your material.",
            "grounded": False,
            "citations": [],
            "source": "knowledge_boundary_check"
        }

    citations = [
        {"page": p["page"], "chunk_id": p["chunk_id"], "similarity": p["similarity_score"]}
        for p in retrieved_passages
    ]

    context_text = "\n\n".join([
        f"[Source: Page {p['page']}]: {p['text']}" for p in retrieved_passages
    ])

    gemini_api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

    if gemini_api_key:
        try:
            # Reuse shared tutor model so Notes RAG and Tutor stay on the same supported ID.
            from app.services.tutor_service import get_tutor_model

            model = get_tutor_model()
            url = (
                f"https://generativelanguage.googleapis.com/v1beta/models/"
                f"{model}:generateContent?key={gemini_api_key}"
            )

            prompt = (
                "You are StudyWise AI Tutor, a personalized academic assistant.\n"
                "Answer the student's question based STRICTLY and ONLY on the provided study notes passages below.\n"
                "If the answer cannot be determined from the passages, say: 'This information is not covered in your uploaded notes.'\n"
                "Always include citations pointing to the relevant page numbers.\n\n"
                f"Context Passages:\n{context_text}\n\n"
                f"Student Question: {question}\n\n"
                "Answer:"
            )

            req_body = {
                "contents": [{"parts": [{"text": prompt}]}]
            }

            req = urllib.request.Request(
                url,
                data=json.dumps(req_body).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )

            with urllib.request.urlopen(req, timeout=10) as response:
                res_data = json.loads(response.read().decode("utf-8"))
                candidate = res_data.get("candidates", [{}])[0]
                text_part = candidate.get("content", {}).get("parts", [{}])[0].get("text", "")
                if text_part:
                    return {
                        "answer": text_part.strip(),
                        "grounded": True,
                        "citations": citations,
                        "source": "gemini_llm"
                    }
        except Exception as e:
            print(f"LLM API call fell back to local synthesis: {e}")

    # Fallback Grounded Extractive Synthesis (offline, reliable, zero-dependency)
    best_chunk = retrieved_passages[0]
    offline_answer = (
        f"Based on your notes (Page {best_chunk['page']}):\n\n"
        f"\"{best_chunk['text']}\"\n\n"
        f"[Note: Answers are strictly grounded in your uploaded documents. "
        f"Add GEMINI_API_KEY to backend .env for full conversational tutoring synthesis.]"
    )

    return {
        "answer": offline_answer,
        "grounded": True,
        "citations": citations,
        "source": "extractive_rag_fallback"
    }
