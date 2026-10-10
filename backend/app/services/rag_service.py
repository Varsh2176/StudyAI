import io
import re
from typing import List, Dict, Any, Tuple
from pypdf import PdfReader
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


def extract_text_from_pdf(file_bytes: bytes) -> List[Dict[str, Any]]:
    """
    Extracts text from a PDF byte stream, preserving page numbers.
    """
    reader = PdfReader(io.BytesIO(file_bytes))
    pages_data = []

    for idx, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        text = re.sub(r"\s+", " ", text).strip()
        if text:
            pages_data.append({
                "page": idx + 1,
                "text": text
            })

    return pages_data


def extract_text_from_txt(file_bytes: bytes) -> List[Dict[str, Any]]:
    """
    Extracts text from plain text byte stream.
    """
    text = file_bytes.decode("utf-8", errors="ignore")
    text = re.sub(r"\s+", " ", text).strip()
    return [{"page": 1, "text": text}]


def chunk_document(
    pages_data: List[Dict[str, Any]],
    chunk_size: int = 150,
    chunk_overlap: int = 30
) -> List[Dict[str, Any]]:
    """
    Splits document pages into chunks with sliding-window word overlap.
    Tracks source page number for citations.
    """
    chunks = []
    chunk_id = 1

    for page_info in pages_data:
        page_num = page_info["page"]
        words = page_info["text"].split()

        if not words:
            continue

        step = max(1, chunk_size - chunk_overlap)
        for i in range(0, len(words), step):
            chunk_words = words[i:i + chunk_size]
            chunk_text = " ".join(chunk_words)

            chunks.append({
                "chunk_id": f"chunk_{chunk_id}",
                "page": page_num,
                "text": chunk_text
            })
            chunk_id += 1

            if i + chunk_size >= len(words):
                break

    return chunks


def retrieve_relevant_passages(
    query: str,
    chunks: List[Dict[str, Any]],
    top_k: int = 3,
    threshold: float = 0.08
) -> List[Dict[str, Any]]:
    """
    Retrieves the top-k most relevant passages for a student question
    using TF-IDF cosine similarity. Returns empty if relevance is below threshold.
    """
    if not chunks or not query.strip():
        return []

    texts = [c["text"] for c in chunks]

    vectorizer = TfidfVectorizer(stop_words="english")
    try:
        tfidf_matrix = vectorizer.fit_transform(texts)
        query_vec = vectorizer.transform([query])
        scores = cosine_similarity(query_vec, tfidf_matrix).flatten()
    except Exception:
        # In case vocabulary is empty or uninformative
        return []

    scored_chunks = []
    for idx, score in enumerate(scores):
        if score >= threshold:
            scored_chunks.append({
                "chunk_id": chunks[idx]["chunk_id"],
                "page": chunks[idx]["page"],
                "text": chunks[idx]["text"],
                "similarity_score": round(float(score), 4)
            })

    # Sort descending by similarity
    scored_chunks.sort(key=lambda x: x["similarity_score"], reverse=True)
    return scored_chunks[:top_k]
