"""
Local extractive Learning Hub tools from owned document text.

No Gemini required. Output is always labelled as local/extractive — never presented
as LLM-generated. Only uses text present in the student's uploaded documents.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Sequence, Tuple


LOCAL_PROVIDER = "local_extractive"
LOCAL_DISCLAIMER = (
    "Local extractive mode — built only from your uploaded document text. "
    "This is not a Gemini/LLM-generated answer. Verify against your notes."
)

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
_DEFINITION_PATTERNS = [
    re.compile(r"^(?P<term>[A-Z][\w\s\-/]{1,60}?)\s+(?:is|are|means|refers to)\s+(?P<defn>.+)$", re.I),
    re.compile(r"^(?P<term>[A-Za-z][\w\s\-/]{1,40})\s*[:\-–]\s+(?P<defn>.{8,220})$"),
]
_HEADING_LINE = re.compile(r"^[A-Z][\w\s\-/,:]{2,70}$")
_WORD = re.compile(r"[A-Za-z][A-Za-z\-']{2,}")


class LocalStudyToolsError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def collect_pages_from_records(records: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Flatten page dicts with filename metadata from document records."""
    pages: List[Dict[str, Any]] = []
    for record in records:
        filename = str(record.get("filename") or "document.pdf")
        doc_id = str(record.get("document_id") or "")
        for page in record.get("pages") or []:
            text = _normalize_whitespace(str(page.get("text") or ""))
            if len(text) < 20:
                continue
            pages.append(
                {
                    "document_id": doc_id,
                    "filename": filename,
                    "page": page.get("page_number") or page.get("page") or 1,
                    "text": text,
                }
            )
    return pages


def _sentences_from_pages(pages: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for page in pages:
        for raw in _SENTENCE_SPLIT.split(page["text"]):
            sentence = _normalize_whitespace(raw)
            if 40 <= len(sentence) <= 280:
                out.append({**page, "sentence": sentence})
    return out


def _topic_filter(items: Sequence[Dict[str, Any]], topic: Optional[str], key: str = "sentence") -> List[Dict[str, Any]]:
    if not topic or not topic.strip():
        return list(items)
    tokens = [t.lower() for t in _WORD.findall(topic) if len(t) > 2]
    if not tokens:
        return list(items)
    scored: List[Tuple[int, Dict[str, Any]]] = []
    for item in items:
        text = str(item.get(key) or "").lower()
        hits = sum(1 for tok in tokens if tok in text)
        if hits:
            scored.append((hits, item))
    scored.sort(key=lambda pair: (-pair[0], len(str(pair[1].get(key) or ""))))
    return [item for _, item in scored] if scored else list(items)


def _extract_definitions(sentences: Sequence[Dict[str, Any]]) -> List[Dict[str, str]]:
    defs: List[Dict[str, str]] = []
    seen = set()
    for item in sentences:
        sentence = item["sentence"]
        for pattern in _DEFINITION_PATTERNS:
            match = pattern.match(sentence.rstrip("."))
            if not match:
                continue
            term = _normalize_whitespace(match.group("term"))
            definition = _normalize_whitespace(match.group("defn")).rstrip(".")
            key = term.lower()
            if len(term) < 2 or len(definition) < 8 or key in seen:
                continue
            if term.lower() in {"this", "that", "there", "it", "they", "these", "those"}:
                continue
            seen.add(key)
            defs.append(
                {
                    "term": term,
                    "definition": definition,
                    "source_sentence": sentence,
                    "filename": str(item.get("filename") or ""),
                    "page": str(item.get("page") or ""),
                }
            )
            break
    return defs


def _candidate_terms(sentences: Sequence[Dict[str, Any]], limit: int = 40) -> List[str]:
    counts: Dict[str, int] = {}
    for item in sentences:
        for word in _WORD.findall(item["sentence"]):
            if word[0].isupper() or len(word) >= 6:
                key = word.lower()
                if key in {"this", "that", "with", "from", "which", "their", "about", "there"}:
                    continue
                counts[key] = counts.get(key, 0) + 1
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [w for w, _ in ranked[:limit]]


def build_local_summary(
    pages: Sequence[Dict[str, Any]],
    *,
    topic: Optional[str] = None,
    max_bullets: int = 8,
) -> Dict[str, Any]:
    sentences = _topic_filter(_sentences_from_pages(pages), topic)
    if not sentences:
        raise LocalStudyToolsError(
            "No usable sentences found in your documents. Upload a text-extractable PDF first.",
            status_code=409,
        )
    # Prefer mid-length informative sentences; keep source order after scoring.
    ranked = sorted(
        enumerate(sentences),
        key=lambda pair: (-min(len(pair[1]["sentence"]), 180), pair[0]),
    )
    chosen = []
    seen = set()
    for _, item in ranked:
        s = item["sentence"]
        key = s.lower()[:80]
        if key in seen:
            continue
        seen.add(key)
        chosen.append(item)
        if len(chosen) >= max_bullets:
            break
    chosen.sort(key=lambda item: (str(item.get("filename")), int(item.get("page") or 0)))
    bullets = [
        f"- {item['sentence']} ({item.get('filename')}, p.{item.get('page')})"
        for item in chosen
    ]
    header = "Local extractive summary"
    if topic and topic.strip():
        header += f" (filtered by topic: {topic.strip()})"
    text = (
        f"[{LOCAL_DISCLAIMER}]\n\n{header}\n\n"
        + "\n".join(bullets)
    )
    return {
        "mode": "local",
        "provider": LOCAL_PROVIDER,
        "label": "Local",
        "disclaimer": LOCAL_DISCLAIMER,
        "summary": text,
        "bullet_count": len(bullets),
        "sources": [
            {"filename": i.get("filename"), "page": i.get("page")} for i in chosen
        ],
    }


def build_local_flashcards(
    pages: Sequence[Dict[str, Any]],
    *,
    topic: Optional[str] = None,
    count: int = 8,
) -> Dict[str, Any]:
    count = max(3, min(int(count), 20))
    sentences = _topic_filter(_sentences_from_pages(pages), topic)
    definitions = _extract_definitions(sentences)
    cards: List[Dict[str, str]] = []
    for item in definitions:
        cards.append(
            {
                "front": f"What is {item['term']}?",
                "back": item["definition"],
            }
        )
        if len(cards) >= count:
            break
    # Fallback: prompt/answer from whole sentences (still extractive, not invented).
    if len(cards) < count:
        for item in sentences:
            s = item["sentence"]
            if len(s) < 50:
                continue
            cards.append(
                {
                    "front": f"Recall from {item.get('filename')} (p.{item.get('page')}): complete this note",
                    "back": s,
                }
            )
            if len(cards) >= count:
                break
    if len(cards) < 3:
        raise LocalStudyToolsError(
            "Could not extract enough flashcard material from your documents. "
            "Upload notes with clearer definitions or longer sentences.",
            status_code=409,
        )
    return {
        "mode": "local",
        "provider": LOCAL_PROVIDER,
        "label": "Local",
        "disclaimer": LOCAL_DISCLAIMER,
        "cards": cards[:count],
    }


def build_local_practice(
    pages: Sequence[Dict[str, Any]],
    *,
    topic: Optional[str] = None,
    count: int = 5,
) -> Dict[str, Any]:
    count = max(3, min(int(count), 15))
    sentences = _topic_filter(_sentences_from_pages(pages), topic)
    terms = _candidate_terms(sentences)
    questions: List[Dict[str, Any]] = []
    for item in sentences:
        sentence = item["sentence"]
        words = _WORD.findall(sentence)
        # Prefer a content word that appears in the sentence and in term ranks.
        answer = None
        for term in terms:
            for w in words:
                if w.lower() == term and len(w) >= 4:
                    answer = w
                    break
            if answer:
                break
        if not answer:
            continue
        blanked = re.sub(rf"\b{re.escape(answer)}\b", "______", sentence, count=1)
        if "______" not in blanked:
            continue
        questions.append(
            {
                "id": f"local-q-{len(questions)+1}",
                "question": f"Fill in the blank (from your notes, p.{item.get('page')}): {blanked}",
                "options": [],
                "answer": answer,
                "explanation": f"Extracted from {item.get('filename')} page {item.get('page')}.",
            }
        )
        if len(questions) >= count:
            break
    if len(questions) < 3:
        raise LocalStudyToolsError(
            "Could not build enough practice questions from your documents. "
            "Upload text-rich PDFs and try again.",
            status_code=409,
        )
    return {
        "mode": "local",
        "provider": LOCAL_PROVIDER,
        "label": "Local",
        "disclaimer": LOCAL_DISCLAIMER,
        "questions": questions[:count],
    }


def build_local_mindmap(
    pages: Sequence[Dict[str, Any]],
    *,
    topic: Optional[str] = None,
) -> Dict[str, Any]:
    root = (topic or "").strip() or (
        pages[0]["filename"].rsplit(".", 1)[0] if pages else "Document outline"
    )
    headings: List[str] = []
    seen = set()
    for page in pages:
        for line in re.split(r"[\n\r]+", page.get("text") or ""):
            candidate = _normalize_whitespace(line)
            if not candidate or len(candidate) > 70 or candidate.endswith("."):
                continue
            if not _HEADING_LINE.match(candidate):
                # Also accept short Title-like fragments without trailing punctuation.
                if not (3 <= len(candidate) <= 60 and candidate[0].isupper()):
                    continue
            key = candidate.lower()
            if key in seen:
                continue
            seen.add(key)
            headings.append(candidate)
            if len(headings) >= 12:
                break
        if len(headings) >= 12:
            break

    children: List[Dict[str, Any]] = []
    if headings:
        for heading in headings[:8]:
            children.append({"label": heading, "children": []})
    else:
        # Fallback: top sentences as outline nodes (still extractive).
        sentences = _topic_filter(_sentences_from_pages(pages), topic)[:6]
        for item in sentences:
            label = item["sentence"]
            if len(label) > 70:
                label = label[:67].rstrip() + "…"
            children.append({"label": label, "children": []})

    if not children:
        raise LocalStudyToolsError(
            "Could not extract an outline from your documents. Upload notes with headings or clearer structure.",
            status_code=409,
        )

    return {
        "mode": "local",
        "provider": LOCAL_PROVIDER,
        "label": "Local",
        "disclaimer": LOCAL_DISCLAIMER,
        "tree": {"topic": root, "children": children},
        "note": "Rule-based outline from document headings/sentences — not semantic AI generation.",
    }


def build_local_mock_exam(
    pages: Sequence[Dict[str, Any]],
    *,
    topic: Optional[str] = None,
    count: int = 5,
) -> Dict[str, Any]:
    count = max(3, min(int(count), 12))
    practice = build_local_practice(pages, topic=topic, count=count)
    terms = _candidate_terms(_sentences_from_pages(pages), limit=60)
    questions: List[Dict[str, Any]] = []
    for q in practice["questions"]:
        answer = q["answer"]
        distractors = []
        for term in terms:
            # Keep original casing approximation from term list (lowercase); capitalize lightly.
            option = term if term[:1].isupper() else term
            if option.lower() == answer.lower():
                continue
            if option not in distractors:
                distractors.append(option)
            if len(distractors) >= 3:
                break
        if len(distractors) < 2:
            continue
        options = [answer] + distractors[:3]
        # Stable shuffle without randomness for reproducibility in tests.
        options = sorted(set(options), key=lambda s: (s.lower() != answer.lower(), s.lower()))
        questions.append(
            {
                "id": q["id"].replace("local-q", "local-exam"),
                "question": q["question"].replace("Fill in the blank", "Choose the missing term"),
                "options": options,
                "answer": answer,
                "explanation": q["explanation"] + " Distractors are other terms found in your notes.",
            }
        )
        if len(questions) >= count:
            break
    if len(questions) < 3:
        raise LocalStudyToolsError(
            "Could not build a reliable local mock exam from your documents. "
            "Upload richer notes or try Practice Questions first.",
            status_code=409,
        )
    return {
        "mode": "local",
        "provider": LOCAL_PROVIDER,
        "label": "Local",
        "disclaimer": LOCAL_DISCLAIMER,
        "questions": questions[:count],
    }


def generate_local_tool(
    tool: str,
    pages: Sequence[Dict[str, Any]],
    *,
    topic: Optional[str] = None,
    count: Optional[int] = None,
) -> Dict[str, Any]:
    if not pages:
        raise LocalStudyToolsError(
            "No extractable document text found for this student. "
            "Upload a PDF on Documents first (OCR is not available for scanned-only files).",
            status_code=409,
        )
    name = (tool or "").strip().lower()
    if name in {"summary", "summaries"}:
        return build_local_summary(pages, topic=topic, max_bullets=count or 8)
    if name in {"flashcards", "flashcard"}:
        return build_local_flashcards(pages, topic=topic, count=count or 8)
    if name in {"practice", "practice_questions"}:
        return build_local_practice(pages, topic=topic, count=count or 5)
    if name in {"mindmap", "mind_map", "mindmaps"}:
        return build_local_mindmap(pages, topic=topic)
    if name in {"mock_exam", "mock", "exam"}:
        return build_local_mock_exam(pages, topic=topic, count=count or 5)
    raise LocalStudyToolsError(
        f"Unsupported local tool '{tool}'. Use summary, flashcards, practice, mindmap, or mock_exam.",
        status_code=422,
    )
