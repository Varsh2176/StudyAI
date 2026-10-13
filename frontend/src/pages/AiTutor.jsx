import { useState, useEffect, useRef, useCallback } from "react";
import { Link } from "react-router-dom";
import API from "../services/api";
import {
  Badge,
  Button,
  Card,
  ErrorMessage,
  Input,
  Skeleton,
  Textarea,
} from "../components/ui";

const MAX_QUESTION_LENGTH = 2000;
const TUTOR_TIMEOUT_MS = 25000;

const EXAMPLE_PROMPTS = [
  "Explain the difference between supervised and unsupervised learning with a simple example.",
  "What is a process control block in operating systems, and why does it matter?",
  "Walk me through Big-O of binary search versus linear search in plain language.",
];

function formatAnswerParts(text) {
  if (!text) return [{ type: "text", value: "" }];
  const parts = [];
  const fence = /```([\s\S]*?)```/g;
  let lastIndex = 0;
  let match;
  while ((match = fence.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push({ type: "text", value: text.slice(lastIndex, match.index) });
    }
    parts.push({ type: "code", value: match[1].replace(/^\w*\n/, "") });
    lastIndex = match.index + match[0].length;
  }
  if (lastIndex < text.length) {
    parts.push({ type: "text", value: text.slice(lastIndex) });
  }
  return parts.length ? parts : [{ type: "text", value: text }];
}

function renderTextBlock(value, keyPrefix) {
  const lines = String(value).split("\n");
  const nodes = [];
  let listItems = [];

  const flushList = () => {
    if (listItems.length === 0) return;
    nodes.push(
      <ul key={`${keyPrefix}-ul-${nodes.length}`}>
        {listItems.map((item, i) => (
          <li key={`${keyPrefix}-li-${i}`}>{item}</li>
        ))}
      </ul>
    );
    listItems = [];
  };

  lines.forEach((line, i) => {
    const bullet = line.match(/^\s*[-*]\s+(.*)$/);
    if (bullet) {
      listItems.push(bullet[1]);
      return;
    }
    flushList();
    if (line.trim() === "") {
      nodes.push(<br key={`${keyPrefix}-br-${i}`} />);
    } else {
      nodes.push(<p key={`${keyPrefix}-p-${i}`}>{line}</p>);
    }
  });
  flushList();
  return nodes;
}

function MessageBody({ text }) {
  const parts = formatAnswerParts(text);
  return (
    <div className="sw-tutor-bubble-body">
      {parts.map((part, idx) =>
        part.type === "code" ? (
          <pre key={`code-${idx}`}>
            <code>{part.value}</code>
          </pre>
        ) : (
          <span key={`text-${idx}`}>{renderTextBlock(part.value, `t${idx}`)}</span>
        )
      )}
    </div>
  );
}

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
      setQuestion(trimmed);
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

  const applyExamplePrompt = (prompt) => {
    if (asking) return;
    setQuestion(prompt);
    setError("");
    if (textareaRef.current) {
      textareaRef.current.focus();
    }
  };

  return (
    <div className="sw-tutor page-container">
      <div className="sw-tutor-hero">
        <section className="sw-tutor-intro" aria-labelledby="tutor-heading">
          <p className="sw-tutor-eyebrow">Gemini-powered help</p>
          <h2 id="tutor-heading">AI study tutor</h2>
          <p>
            Ask academic questions and get clear, student-friendly explanations.
            Conversation history stays in this browser session and is not saved to the database.
          </p>
        </section>
        <div className="sw-tutor-hero-actions">
          <Link to="/documents" className="sw-btn sw-btn--secondary sw-btn--sm">
            Ask about uploaded PDFs
          </Link>
        </div>
      </div>

      <Card title="Tutor service" className="sw-tutor-status-card">
        <div className="sw-tutor-status-row">
          <div>
            {statusLoading ? (
              <Skeleton variant="line" />
            ) : status?.configured ? (
              <p className="sw-tutor-status-meta">
                <Badge variant="success">Ready</Badge>{" "}
                Provider: {status.provider}
                {status.model ? ` · Model: ${status.model}` : ""}
              </p>
            ) : (
              <p className="sw-tutor-status-meta">
                <Badge variant="danger">Not configured</Badge>{" "}
                {status?.message || "Set GEMINI_API_KEY in backend/.env"}
              </p>
            )}
          </div>
          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={loadStatus}
            loading={statusLoading}
            disabled={statusLoading}
          >
            Refresh status
          </Button>
        </div>
        {!statusLoading && !status?.configured ? (
          <div className="sw-tutor-config-note">
            To enable live answers, add <code>GEMINI_API_KEY</code> to <code>backend/.env</code>, restart
            uvicorn, then refresh this status. The chat UI still works for testing empty/error handling
            without credentials — responses will show a clear configuration error (not a fake AI answer).
            For questions grounded in your PDFs, use{" "}
            <Link to="/documents">Documents → Ask your notes</Link>.
          </div>
        ) : (
          <p className="sw-tutor-docs-link">
            Prefer answers grounded in your uploaded notes?{" "}
            <Link to="/documents#ask-notes">Open document RAG on Documents</Link>.
          </p>
        )}
      </Card>

      <Card className="sw-tutor-chat-card">
        <div className="sw-tutor-toolbar">
          <h3>Conversation</h3>
          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={handleNewConversation}
            disabled={asking || messages.length === 0}
          >
            New conversation
          </Button>
        </div>

        <div className="sw-tutor-meta-grid">
          <Input
            id="tutor-email"
            label="Student email (optional profile context)"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="Uses saved registration email when available"
            hint="If a profile exists for this email, course/subjects may be used as light context only."
          />
          <Input
            id="tutor-subject"
            label="Subject / topic (optional)"
            type="text"
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
            placeholder="e.g. Operating Systems"
            maxLength={120}
          />
        </div>

        {error ? (
          <ErrorMessage
            message={error}
            onRetry={lastFailedQuestion ? handleRetry : undefined}
            retryLabel="Retry last question"
          />
        ) : null}

        <div className="sw-tutor-chat" aria-live="polite" aria-relevant="additions">
          {messages.length === 0 && !asking ? (
            <div className="sw-tutor-empty">
              <strong>Start a conversation</strong>
              <p>Pick an example or type your own academic question below.</p>
              <p>Tip: Press Enter to send, Shift+Enter for a new line.</p>
              <div className="sw-tutor-examples">
                {EXAMPLE_PROMPTS.map((prompt) => (
                  <button
                    key={prompt}
                    type="button"
                    className="sw-tutor-example"
                    onClick={() => applyExamplePrompt(prompt)}
                    disabled={asking}
                  >
                    {prompt}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            messages.map((msg, idx) => (
              <div
                key={`${msg.role}-${idx}`}
                className={[
                  "sw-tutor-bubble",
                  msg.role === "user" ? "sw-tutor-bubble--user" : "sw-tutor-bubble--assistant",
                  msg.isError ? "sw-tutor-bubble--error" : "",
                ]
                  .filter(Boolean)
                  .join(" ")}
              >
                <div className="sw-tutor-role">
                  {msg.role === "user" ? "You" : msg.isError ? "Tutor error" : "AI Tutor"}
                </div>
                <MessageBody text={msg.text} />
                {msg.model_used && !msg.isError ? (
                  <div className="sw-tutor-meta">
                    {msg.provider} · {msg.model_used}
                    {msg.profile_context_used ? " · profile context used" : ""}
                  </div>
                ) : null}
              </div>
            ))
          )}

          {asking ? (
            <div className="sw-tutor-loading" aria-busy="true">
              <div className="sw-tutor-typing" aria-hidden="true">
                <span />
                <span />
                <span />
              </div>
              Generating a clear explanation…
            </div>
          ) : null}
          <div ref={chatEndRef} />
        </div>

        <form onSubmit={handleSubmit} className="sw-tutor-composer">
          <Textarea
            id="tutor-question"
            label="Academic question"
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
          <div className="sw-tutor-composer-actions">
            <span id="tutor-char-count" className="sw-tutor-char">
              {question.length}/{MAX_QUESTION_LENGTH}
            </span>
            <Button
              type="submit"
              variant="primary"
              loading={asking}
              disabled={asking || !question.trim()}
            >
              {asking ? "Thinking..." : "Ask tutor"}
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
}

export default AiTutor;
