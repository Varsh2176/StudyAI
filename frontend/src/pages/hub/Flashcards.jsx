import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorMessage,
  Input,
  Skeleton,
  Textarea,
} from "../../components/ui";
import {
  fetchTutorStatus,
  formatApiError,
  generateHubContent,
  modeBadgeLabel,
  parseJsonFromAnswer,
} from "../../utils/hubAi";

function normalizeCards(parsed) {
  const list = Array.isArray(parsed)
    ? parsed
    : Array.isArray(parsed?.cards)
      ? parsed.cards
      : null;
  if (!list) return null;
  const cards = list
    .map((item) => ({
      front: String(item?.front || item?.question || item?.term || "").trim(),
      back: String(item?.back || item?.answer || item?.definition || "").trim(),
    }))
    .filter((c) => c.front && c.back);
  return cards.length ? cards : null;
}

function Flashcards() {
  const [email, setEmail] = useState(() => localStorage.getItem("student_email") || "");
  const [topic, setTopic] = useState("");
  const [count, setCount] = useState(8);
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [rawAnswer, setRawAnswer] = useState("");
  const [cards, setCards] = useState([]);
  const [index, setIndex] = useState(0);
  const [flipped, setFlipped] = useState(false);
  const [meta, setMeta] = useState(null);

  useEffect(() => {
    let cancelled = false;
    void fetchTutorStatus()
      .then((data) => {
        if (!cancelled) setStatus(data);
      })
      .catch(() => {
        if (!cancelled) {
          setStatus({ configured: false, message: "Could not reach generation status." });
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const handleGenerate = async (e) => {
    e.preventDefault();
    setError("");
    setCards([]);
    setRawAnswer("");
    setIndex(0);
    setFlipped(false);
    setMeta(null);

    const trimmedEmail = email.trim();
    if (!trimmedEmail) {
      setError("Enter your student email so local flashcards can use your uploaded documents.");
      return;
    }
    localStorage.setItem("student_email", trimmedEmail);
    window.dispatchEvent(new Event("studyai-identity-changed"));

    const n = Math.min(20, Math.max(3, Number(count) || 8));
    setLoading(true);
    try {
      const geminiPrompt = [
        `Create ${n} study flashcards for: ${topic.trim() || "general study revision"}.`,
        "Return ONLY valid JSON (no markdown prose outside JSON) in this shape:",
        '{"cards":[{"front":"...","back":"..."}]}',
        "Front should be a short prompt; back should be a precise answer suitable for active recall.",
      ].join("\n");
      const data = await generateHubContent({
        tool: "flashcards",
        email: trimmedEmail,
        topic: topic.trim() || undefined,
        count: n,
        geminiConfigured: Boolean(status?.configured),
        geminiPrompt: topic.trim() ? geminiPrompt : undefined,
      });

      if (data.mode === "local" && Array.isArray(data.cards)) {
        setCards(data.cards);
        setMeta({
          provider: data.provider,
          label: modeBadgeLabel(data.label || data.mode),
          disclaimer: data.disclaimer,
        });
        setRawAnswer("");
        return;
      }

      setRawAnswer(data.answer || "");
      setMeta({
        provider: data.provider,
        model_used: data.model_used,
        label: modeBadgeLabel(data.label || data.mode),
      });
      const parsed = parseJsonFromAnswer(data.answer);
      const normalized = normalizeCards(parsed);
      if (!normalized) {
        setError(
          "Gemini responded, but flashcards JSON could not be parsed. The raw answer is shown below."
        );
        return;
      }
      setCards(normalized);
    } catch (err) {
      setError(formatApiError(err));
    } finally {
      setLoading(false);
    }
  };

  const current = cards[index];

  return (
    <div className="sw-hub-tool page-container">
      <div className="sw-hub-tool-hero">
        <p className="sw-hub-eyebrow">Revise</p>
        <h2>Flashcards</h2>
        <p>
          Generate active-recall cards from your uploaded document text (local extractive mode).
          If Gemini is configured and a topic is provided, topic-only Gemini generation is used as a
          fallback. Nothing is invented client-side.
        </p>
        <div className="sw-hub-tool-links">
          <Link to="/hub" className="sw-btn sw-btn--ghost sw-btn--sm">
            ← Learning Hub
          </Link>
          <Link to="/documents" className="sw-btn sw-btn--secondary sw-btn--sm">
            Documents
          </Link>
        </div>
      </div>

      <Card title="Generation status">
        {status == null ? (
          <Skeleton variant="line" />
        ) : (
          <p className="sw-hub-tool-status-meta">
            <Badge variant="success">Local available</Badge> uses your Documents text
            {status.configured ? (
              <>
                {" "}
                · <Badge variant="info">Gemini-enhanced optional</Badge> {status.provider}
                {status.model ? ` · ${status.model}` : ""}
              </>
            ) : (
              <>
                {" "}
                · <Badge variant="warning">Gemini optional</Badge>{" "}
                {status.message || "Set GEMINI_API_KEY for topic-only generation."}
              </>
            )}
          </p>
        )}
      </Card>

      <Card title="Generate deck">
        <form className="sw-hub-tool-form" onSubmit={handleGenerate}>
          <Input
            id="fc-email"
            label="Student email *"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            hint="Required for local document-based flashcards."
            required
          />
          <Textarea
            id="fc-topic"
            label="Topic filter (optional for local)"
            rows={2}
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            placeholder="e.g. Binary search trees"
            hint="Filters local extraction; required only when falling back to Gemini topic-only mode."
          />
          <Input
            id="fc-count"
            label="Number of cards"
            type="number"
            min="3"
            max="20"
            value={count}
            onChange={(e) => setCount(e.target.value)}
          />
          {error ? <ErrorMessage message={error} /> : null}
          <Button
            type="submit"
            variant="primary"
            loading={loading}
            disabled={loading || !email.trim()}
          >
            {loading ? "Generating…" : "Generate flashcards"}
          </Button>
        </form>
      </Card>

      {loading ? <Skeleton variant="card" /> : null}

      {!loading && cards.length === 0 && !rawAnswer ? (
        <EmptyState
          title="No flashcards yet"
          description="Enter your email (and upload notes) for local flashcards, or configure Gemini for topic-only generation."
        />
      ) : null}

      {cards.length > 0 ? (
        <Card title={`Deck · ${index + 1} / ${cards.length}`}>
          {meta ? (
            <div className="sw-hub-tool-meta">
              {meta.provider}
              {meta.model_used ? ` · ${meta.model_used}` : ""}
            </div>
          ) : null}
          <button
            type="button"
            className={`sw-hub-flashcard${flipped ? " sw-hub-flashcard--flipped" : ""}`}
            onClick={() => setFlipped((v) => !v)}
            aria-label={flipped ? "Show front" : "Show back"}
          >
            <span className="sw-hub-flashcard-label">{flipped ? "Answer" : "Prompt"}</span>
            <span className="sw-hub-flashcard-text">
              {flipped ? current.back : current.front}
            </span>
            <span className="sw-hub-flashcard-hint">Click to flip</span>
          </button>
          <div className="sw-hub-tool-nav">
            <Button
              type="button"
              variant="secondary"
              size="sm"
              disabled={index === 0}
              onClick={() => {
                setIndex((i) => Math.max(0, i - 1));
                setFlipped(false);
              }}
            >
              Previous
            </Button>
            <Button
              type="button"
              variant="secondary"
              size="sm"
              disabled={index >= cards.length - 1}
              onClick={() => {
                setIndex((i) => Math.min(cards.length - 1, i + 1));
                setFlipped(false);
              }}
            >
              Next
            </Button>
          </div>
        </Card>
      ) : null}

      {rawAnswer && cards.length === 0 ? (
        <Card title="Raw generation response">
          <div className="sw-hub-tool-output">{rawAnswer}</div>
        </Card>
      ) : null}
    </div>
  );
}

export default Flashcards;
