import { useState, useEffect, useRef, useCallback } from "react";
import API from "../services/api";

const MAX_QUESTION_LENGTH = 2000;
const TUTOR_TIMEOUT_MS = 25000;

function AiTutor() {
  const [email, setEmail] = useState(() => localStorage.getItem("student_email") || "");
  const [subject, setSubject] = useState("");
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState([]);
  const [asking, setAsking] = useState(false);
  const [error, setError] = useState("");
  const [status, setStatus] = useState(null);
  const [statusLoading, setStatusLoading] = useState(true);
  const [lastFailedQuestion, setLastFailedQuestion] = useState(null);
  const chatEndRef = useRef(null);
  const textareaRef = useRef(null);

  const scrollToBottom = useCallback(() => {
    if (chatEndRef.current) {
      chatEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, []);

  const loadStatus = useCallback(async () => {
    setStatusLoading(true);
    try {
      const res = await API.get("/ai/tutor/status", { timeout: 8000 });
      setStatus(res.data);
    } catch {
      setStatus({
        configured: false,
        message: "Could not reach the AI Tutor status endpoint. Is the backend running on port 8000?"
      });
    } finally {
      setStatusLoading(false);
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadStatus();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [loadStatus]);

  useEffect(() => {
    scrollToBottom();
  }, [messages, asking, scrollToBottom]);

  const buildHistoryPayload = (currentMessages) =>
    currentMessages
      .filter((m) => m.role === "user" || m.role === "assistant")
      .filter((m) => !m.isError)
      .slice(-20)
      .map((m) => ({ role: m.role, content: m.text }));

  const askTutor = async (rawQuestion, priorMessages) => {
    const trimmed = (rawQuestion || "").trim();
    if (!trimmed) {
      setError("Please enter an academic question before sending.");
      return;
    }
    if (trimmed.length > MAX_QUESTION_LENGTH) {
      setError(`Question is too long (max ${MAX_QUESTION_LENGTH} characters).`);
      return;
    }

    setError("");
    setLastFailedQuestion(null);
    setAsking(true);

    const historyForRequest = buildHistoryPayload(priorMessages);
    const nextMessages = [...priorMessages, { role: "user", text: trimmed }];
    setMessages(nextMessages);
    setQuestion("");

    try {
      const res = await API.post(
        "/ai/tutor",
        {
          question: trimmed,
          email: email || undefined,
          subject: subject.trim() || undefined,
          conversation_history: historyForRequest,
          include_profile_context: Boolean(email)
        },
        { timeout: TUTOR_TIMEOUT_MS }
      );

      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          text: res.data.answer,
          provider: res.data.provider,
          model_used: res.data.model_used,
          disclaimer: res.data.disclaimer,
          profile_context_used: res.data.profile_context_used
        }
      ]);
    } catch (err) {
      const detail =
        err.code === "ECONNABORTED"
          ? "The tutor request timed out. Please try again with a shorter question."
          : err.response?.data?.detail ||
            err.message ||
            "Failed to reach the AI Tutor. Ensure the backend is running.";

      const messageText = Array.isArray(detail)
        ? detail.map((d) => d.msg || JSON.stringify(d)).join(" ")
        : String(detail);

      setError(messageText);
      setLastFailedQuestion(trimmed);
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          text: messageText,
          isError: true
        }
      ]);
    } finally {
      setAsking(false);
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (asking) return;
    void askTutor(question, messages);
  };

  const handleRetry = () => {
    if (asking || !lastFailedQuestion) return;
    const withoutFailedTail = [...messages];
    // Remove trailing user + error assistant pair from the failed attempt.
    while (withoutFailedTail.length > 0) {
      const last = withoutFailedTail[withoutFailedTail.length - 1];
      if (last.isError || last.role === "user") {
        withoutFailedTail.pop();
        if (last.role === "user") break;
        continue;
      }
      break;
    }
    void askTutor(lastFailedQuestion, withoutFailedTail);
  };

  const handleNewConversation = () => {
    if (asking) return;
    setMessages([]);
    setQuestion("");
    setError("");
    setLastFailedQuestion(null);
    if (textareaRef.current) {
      textareaRef.current.focus();
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (!asking && question.trim()) {
        void askTutor(question, messages);
      }
    }
  };

  return (
    <div className="page-container tutor-page">
      <div className="page-header">
        <h1>AI Study Tutor</h1>
        <p>
          Ask academic questions and get clear, student-friendly explanations.
          Conversation history stays in this browser session and is not saved to the database.
        </p>
      </div>

      <div className="card tutor-status-card">
        <div className="tutor-status-row">
          <div>
            <div className="stat-card-title">Tutor Service</div>
            {statusLoading ? (
              <p style={{ margin: "0.35rem 0 0", color: "var(--text-muted)" }}>Checking configuration...</p>
            ) : status?.configured ? (
              <p style={{ margin: "0.35rem 0 0" }}>
                <span className="badge badge-low">Ready</span>{" "}
                <span style={{ color: "var(--text-muted)", fontSize: "0.9rem" }}>
                  Provider: {status.provider} · Model: {status.model}
                </span>
              </p>
            ) : (
              <p style={{ margin: "0.35rem 0 0" }}>
                <span className="badge badge-high">Not configured</span>{" "}
                <span style={{ color: "var(--text-muted)", fontSize: "0.9rem" }}>
                  {status?.message || "Set GEMINI_API_KEY in backend/.env"}
                </span>
              </p>
            )}
          </div>
          <button type="button" className="btn btn-secondary btn-sm" onClick={loadStatus} disabled={statusLoading}>
            Refresh Status
          </button>
        </div>
        {!statusLoading && !status?.configured && (
          <div className="alert alert-info" style={{ marginTop: "1rem", marginBottom: 0 }}>
            To enable live answers, add <code>GEMINI_API_KEY</code> to <code>backend/.env</code>, restart
            uvicorn, then refresh this status. The chat UI still works for testing empty/error handling
            without credentials — responses will show a clear configuration error (not a fake AI answer).
          </div>
        )}
      </div>

      <div className="card tutor-chat-card">
        <div className="tutor-chat-toolbar">
          <h2 className="card-title" style={{ margin: 0 }}>Conversation</h2>
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={handleNewConversation}
            disabled={asking || messages.length === 0}
          >
            New Conversation
          </button>
        </div>

        <div className="tutor-meta-grid">
          <div className="form-group">
            <label htmlFor="tutor-email">Student Email (optional profile context)</label>
            <input
              id="tutor-email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="Uses saved registration email when available"
            />
            <span className="form-help">
              If a profile exists for this email, course/subjects may be used as light context only.
            </span>
          </div>
          <div className="form-group">
            <label htmlFor="tutor-subject">Subject / Topic (optional)</label>
            <input
              id="tutor-subject"
              type="text"
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              placeholder="e.g. Operating Systems"
              maxLength={120}
            />
          </div>
        </div>

        {error && (
          <div className="alert alert-danger tutor-error-banner">
            <span>{error}</span>
            {lastFailedQuestion && (
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={handleRetry}
                disabled={asking}
              >
                Retry
              </button>
            )}
          </div>
        )}

        <div className="chat-window tutor-chat-window" aria-live="polite">
          {messages.length === 0 && !asking ? (
            <div className="tutor-empty-state">
              <p style={{ margin: 0, fontWeight: 600 }}>Start a conversation</p>
              <p style={{ margin: "0.5rem 0 0", fontSize: "0.9rem" }}>
                Example: &quot;Explain the difference between supervised and unsupervised learning with a simple example.&quot;
              </p>
              <p style={{ margin: "0.75rem 0 0", fontSize: "0.85rem" }}>
                Tip: Press Enter to send, Shift+Enter for a new line.
              </p>
            </div>
          ) : (
            messages.map((msg, idx) => (
              <div
                key={`${msg.role}-${idx}`}
                className={`chat-bubble ${
                  msg.role === "user" ? "chat-bubble-user" : "chat-bubble-ai"
                } ${msg.isError ? "chat-bubble-error" : ""}`}
              >
                <div className="chat-role-label">
                  {msg.role === "user" ? "You" : msg.isError ? "Tutor error" : "AI Tutor"}
                </div>
                <div style={{ whiteSpace: "pre-wrap" }}>{msg.text}</div>
                {msg.model_used && !msg.isError && (
                  <div className="chat-meta">
                    {msg.provider} · {msg.model_used}
                    {msg.profile_context_used ? " · profile context used" : ""}
                  </div>
                )}
              </div>
            ))
          )}

          {asking && (
            <div className="chat-bubble chat-bubble-ai tutor-loading-bubble" aria-busy="true">
              <div className="chat-role-label">AI Tutor</div>
              <div className="tutor-typing">
                <span />
                <span />
                <span />
              </div>
              Generating a clear explanation...
            </div>
          )}
          <div ref={chatEndRef} />
        </div>

        <form onSubmit={handleSubmit} className="tutor-composer">
          <label htmlFor="tutor-question" className="sr-only">
            Academic question
          </label>
          <textarea
            id="tutor-question"
            ref={textareaRef}
            rows={3}
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask an academic question..."
            disabled={asking}
            maxLength={MAX_QUESTION_LENGTH}
            aria-describedby="tutor-char-count"
          />
          <div className="tutor-composer-actions">
            <span id="tutor-char-count" className="form-help">
              {question.length}/{MAX_QUESTION_LENGTH}
            </span>
            <button
              type="submit"
              className="btn btn-primary"
              disabled={asking || !question.trim()}
            >
              {asking ? "Thinking..." : "Ask Tutor"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default AiTutor;
