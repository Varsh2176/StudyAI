import API, { getApiUnreachableMessage } from "../services/api";

const TUTOR_TIMEOUT_MS = 45000;

export async function fetchTutorStatus() {
  const res = await API.get("/ai/tutor/status", { timeout: 8000 });
  return res.data;
}

export async function askTutor({
  question,
  email,
  subject,
  includeProfileContext = true,
}) {
  const res = await API.post(
    "/ai/tutor",
    {
      question,
      email: email || undefined,
      subject: subject || undefined,
      conversation_history: [],
      include_profile_context: Boolean(email) && includeProfileContext,
    },
    { timeout: TUTOR_TIMEOUT_MS }
  );
  return res.data;
}

export async function listDocuments(email) {
  const trimmed = (email || "").trim();
  if (!trimmed) return [];
  const res = await API.get("/documents", { params: { email: trimmed } });
  return res.data?.documents || [];
}

export async function askDocumentRag({ email, question, documentId, topK = 4 }) {
  const res = await API.post(
    "/documents/rag/ask",
    {
      email: email.trim(),
      question,
      document_id: documentId || undefined,
      top_k: topK,
    },
    { timeout: 45000 }
  );
  return res.data;
}

/**
 * Extract JSON from an LLM answer. Supports fenced ```json blocks or raw JSON.
 * Returns null when parsing fails — callers must not invent structured data.
 */
export function parseJsonFromAnswer(text) {
  if (!text || typeof text !== "string") return null;
  const fenced = text.match(/```(?:json)?\s*([\s\S]*?)```/i);
  const candidate = (fenced ? fenced[1] : text).trim();
  try {
    return JSON.parse(candidate);
  } catch {
    const startObj = candidate.indexOf("{");
    const startArr = candidate.indexOf("[");
    let start = -1;
    if (startObj >= 0 && (startArr < 0 || startObj < startArr)) start = startObj;
    else if (startArr >= 0) start = startArr;
    if (start < 0) return null;
    const closing = candidate[start] === "[" ? "]" : "}";
    const end = candidate.lastIndexOf(closing);
    if (end <= start) return null;
    try {
      return JSON.parse(candidate.slice(start, end + 1));
    } catch {
      return null;
    }
  }
}

export function formatApiError(err) {
  const detail = err?.response?.data?.detail;
  if (Array.isArray(detail)) {
    return detail.map((d) => d.msg || JSON.stringify(d)).join(" ");
  }
  if (typeof detail === "string" && detail.trim()) return detail;
  if (err?.code === "ECONNABORTED") {
    return "The request timed out. Try a shorter topic or try again.";
  }
  if (err?.code === "ERR_NETWORK") {
    return getApiUnreachableMessage();
  }
  return err?.message || "Request failed.";
}
