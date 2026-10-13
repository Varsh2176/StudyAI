import API, { getApiUnreachableMessage } from "../services/api";

// Must exceed backend per-attempt timeout + one retry (see tutor_service defaults).
const TUTOR_TIMEOUT_MS = 90000;

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

/**
 * Document-grounded local Learning Hub tools (no Gemini required).
 * tool: summary | flashcards | practice | mindmap | mock_exam
 */
export async function generateLocalHubTool({
  email,
  tool,
  topic,
  count,
  documentId,
}) {
  const res = await API.post(
    "/ai/hub/local",
    {
      email: email.trim(),
      tool,
      topic: topic || undefined,
      count: count || undefined,
      document_id: documentId || undefined,
    },
    { timeout: 30000 }
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
 * Prefer local extractive tools from documents; optionally fall back to Gemini topic generation.
 * Never invents client-side content when both paths fail.
 */
export async function generateHubContent({
  tool,
  email,
  topic,
  count,
  documentId,
  geminiConfigured,
  geminiPrompt,
  preferGemini = false,
}) {
  const trimmedEmail = (email || "").trim();
  const errors = [];

  const tryLocal = async () => {
    if (!trimmedEmail) {
      throw new Error("Enter your student email to use local document-based tools.");
    }
    return generateLocalHubTool({
      email: trimmedEmail,
      tool,
      topic,
      count,
      documentId,
    });
  };

  const tryGemini = async () => {
    if (!geminiConfigured) {
      throw new Error("Gemini is not configured.");
    }
    if (!geminiPrompt || !String(geminiPrompt).trim()) {
      throw new Error("Missing Gemini prompt.");
    }
    const data = await askTutor({
      question: geminiPrompt,
      email: trimmedEmail || undefined,
      subject: topic || undefined,
    });
    return {
      mode: "gemini",
      provider: data.provider || "gemini",
      label: "Gemini-enhanced",
      disclaimer: data.disclaimer,
      answer: data.answer,
      model_used: data.model_used,
      raw: data,
    };
  };

  if (preferGemini && geminiConfigured) {
    try {
      return await tryGemini();
    } catch (err) {
      errors.push(formatApiError(err));
      try {
        return await tryLocal();
      } catch (localErr) {
        errors.push(formatApiError(localErr));
        throw new Error(errors.filter(Boolean).join(" | "), { cause: localErr });
      }
    }
  }

  try {
    return await tryLocal();
  } catch (localErr) {
    errors.push(formatApiError(localErr));
    if (geminiConfigured && geminiPrompt) {
      try {
        return await tryGemini();
      } catch (gemErr) {
        errors.push(formatApiError(gemErr));
        throw new Error(
          errors.filter(Boolean).join(" | ") ||
            "Could not generate content. Upload documents for local mode or configure GEMINI_API_KEY.",
          { cause: gemErr }
        );
      }
    }
    throw new Error(
      errors.filter(Boolean).join(" | ") ||
        "Could not generate content. Upload documents for local mode or configure GEMINI_API_KEY.",
      { cause: localErr }
    );
  }
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

export function modeBadgeLabel(modeOrLabel) {
  const value = String(modeOrLabel || "").toLowerCase();
  if (value.includes("gemini") || value === "llm" || value === "gemini") return "Gemini-enhanced";
  if (value.includes("local") || value === "retrieval_only") return "Local";
  if (value.includes("planned")) return "Planned";
  return modeOrLabel || "Unknown";
}
