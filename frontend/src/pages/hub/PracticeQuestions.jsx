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
  askTutor,
  fetchTutorStatus,
  formatApiError,
  parseJsonFromAnswer,
} from "../../utils/hubAi";

function normalizeQuestions(parsed) {
  const list = Array.isArray(parsed)
    ? parsed
    : Array.isArray(parsed?.questions)
      ? parsed.questions
      : null;
  if (!list) return null;
  const questions = list
    .map((item, idx) => {
      const question = String(item?.question || item?.prompt || "").trim();
      const options = Array.isArray(item?.options)
        ? item.options.map((o) => String(o)).filter(Boolean)
        : [];
      const answer = String(item?.answer || item?.correct || "").trim();
      const explanation = String(item?.explanation || "").trim();
      if (!question || !answer) return null;
      return {
        id: item?.id || `q-${idx}`,
        question,
        options,
        answer,
        explanation,
      };
    })
    .filter(Boolean);
  return questions.length ? questions : null;
}

function PracticeQuestions() {
  const [email, setEmail] = useState(() => localStorage.getItem("student_email") || "");
  const [topic, setTopic] = useState("");
  const [count, setCount] = useState(5);
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [questions, setQuestions] = useState([]);
  const [rawAnswer, setRawAnswer] = useState("");
  const [revealed, setRevealed] = useState({});
  const [meta, setMeta] = useState(null);

  useEffect(() => {
    let cancelled = false;
    void fetchTutorStatus()
      .then((data) => {
        if (!cancelled) setStatus(data);
      })
      .catch(() => {
        if (!cancelled) {
          setStatus({ configured: false, message: "Could not reach tutor status." });
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const handleGenerate = async (e) => {
    e.preventDefault();
    setError("");
    setQuestions([]);
    setRawAnswer("");
    setRevealed({});
    setMeta(null);

    if (!topic.trim()) {
      setError("Enter a topic for practice questions.");
      return;
    }

    const trimmedEmail = email.trim();
    if (trimmedEmail) {
      localStorage.setItem("student_email", trimmedEmail);
      window.dispatchEvent(new Event("studyai-identity-changed"));
    }

    const n = Math.min(15, Math.max(3, Number(count) || 5));
    setLoading(true);
    try {
      const question = [
        `Create ${n} college-level practice questions on: ${topic.trim()}.`,
        "Return ONLY valid JSON:",
        '{"questions":[{"question":"...","options":["A","B","C","D"],"answer":"...","explanation":"..."}]}',
        "Prefer multiple-choice when possible; answer must match one option when options exist.",
      ].join("\n");
      const data = await askTutor({
        question,
        email: trimmedEmail || undefined,
        subject: topic.trim(),
      });
      setRawAnswer(data.answer || "");
      setMeta({ provider: data.provider, model_used: data.model_used });
      const parsed = parseJsonFromAnswer(data.answer);
      const normalized = normalizeQuestions(parsed);
      if (!normalized) {
        setError(
          "The tutor responded, but practice-question JSON could not be parsed. The raw answer is shown below."
        );
        return;
      }
      setQuestions(normalized);
    } catch (err) {
      setError(formatApiError(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="sw-hub-tool page-container">
      <div className="sw-hub-tool-hero">
        <p className="sw-hub-eyebrow">Practice</p>
        <h2>Practice Questions</h2>
        <p>
          Generate topic drills through the AI Tutor. Questions appear only from a successful,
          parseable API response.
        </p>
        <div className="sw-hub-tool-links">
          <Link to="/hub" className="sw-btn sw-btn--ghost sw-btn--sm">
            ← Learning Hub
          </Link>
          <Link to="/predict" className="sw-btn sw-btn--secondary sw-btn--sm">
            Score prediction
          </Link>
        </div>
      </div>

      <Card title="Tutor status">
        {status == null ? (
          <Skeleton variant="line" />
        ) : status.configured ? (
          <p className="sw-hub-tool-status-meta">
            <Badge variant="success">Ready</Badge> {status.provider}
            {status.model ? ` · ${status.model}` : ""}
          </p>
        ) : (
          <p className="sw-hub-tool-status-meta">
            <Badge variant="danger">Not configured</Badge>{" "}
            {status.message || "Set GEMINI_API_KEY to generate practice questions."}
          </p>
        )}
      </Card>

      <Card title="Generate questions">
        <form className="sw-hub-tool-form" onSubmit={handleGenerate}>
          <Input
            id="pq-email"
            label="Student email (optional)"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          <Textarea
            id="pq-topic"
            label="Topic *"
            rows={2}
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            placeholder="e.g. Database normalization"
            required
          />
          <Input
            id="pq-count"
            label="How many questions"
            type="number"
            min="3"
            max="15"
            value={count}
            onChange={(e) => setCount(e.target.value)}
          />
          {error ? <ErrorMessage message={error} /> : null}
          <Button
            type="submit"
            variant="primary"
            loading={loading}
            disabled={loading || status?.configured === false}
          >
            {loading ? "Generating…" : "Generate practice set"}
          </Button>
        </form>
      </Card>

      {loading ? <Skeleton variant="card" /> : null}

      {!loading && questions.length === 0 && !rawAnswer ? (
        <EmptyState
          title="No questions yet"
          description="Enter a topic and generate when the tutor provider is configured."
        />
      ) : null}

      {questions.length > 0 ? (
        <div className="sw-hub-question-list">
          {meta ? (
            <div className="sw-hub-tool-meta">
              {meta.provider}
              {meta.model_used ? ` · ${meta.model_used}` : ""}
            </div>
          ) : null}
          {questions.map((q, idx) => (
            <Card key={q.id} title={`Question ${idx + 1}`}>
              <p className="sw-hub-question-prompt">{q.question}</p>
              {q.options.length > 0 ? (
                <ul className="sw-hub-question-options">
                  {q.options.map((opt) => (
                    <li key={opt}>{opt}</li>
                  ))}
                </ul>
              ) : null}
              {revealed[q.id] ? (
                <div className="sw-hub-question-answer">
                  <strong>Answer:</strong> {q.answer}
                  {q.explanation ? <p>{q.explanation}</p> : null}
                </div>
              ) : (
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  onClick={() => setRevealed((prev) => ({ ...prev, [q.id]: true }))}
                >
                  Reveal answer
                </Button>
              )}
            </Card>
          ))}
        </div>
      ) : null}

      {rawAnswer && questions.length === 0 ? (
        <Card title="Raw tutor response">
          <div className="sw-hub-tool-output">{rawAnswer}</div>
        </Card>
      ) : null}
    </div>
  );
}

export default PracticeQuestions;
