import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorMessage,
  Input,
  ProgressBar,
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

function normalizeExam(parsed) {
  const list = Array.isArray(parsed)
    ? parsed
    : Array.isArray(parsed?.questions)
      ? parsed.questions
      : null;
  if (!list) return null;
  const questions = list
    .map((item, idx) => {
      const question = String(item?.question || "").trim();
      const options = Array.isArray(item?.options)
        ? item.options.map((o) => String(o)).filter(Boolean)
        : [];
      const answer = String(item?.answer || "").trim();
      const explanation = String(item?.explanation || "").trim();
      if (!question || options.length < 2 || !answer) return null;
      return {
        id: item?.id || `exam-${idx}`,
        question,
        options,
        answer,
        explanation,
      };
    })
    .filter(Boolean);
  return questions.length >= 3 ? questions : null;
}

function answersMatch(selected, correct) {
  const a = String(selected || "").trim().toLowerCase();
  const b = String(correct || "").trim().toLowerCase();
  if (!a || !b) return false;
  return a === b || a.includes(b) || b.includes(a);
}

function MockExam() {
  const [email, setEmail] = useState(() => localStorage.getItem("student_email") || "");
  const [topic, setTopic] = useState("");
  const [count, setCount] = useState(5);
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [questions, setQuestions] = useState([]);
  const [rawAnswer, setRawAnswer] = useState("");
  const [answers, setAnswers] = useState({});
  const [submitted, setSubmitted] = useState(false);
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

  const score = useMemo(() => {
    if (!submitted || questions.length === 0) return null;
    let correct = 0;
    questions.forEach((q) => {
      if (answersMatch(answers[q.id], q.answer)) correct += 1;
    });
    return { correct, total: questions.length, percent: Math.round((correct / questions.length) * 100) };
  }, [submitted, questions, answers]);

  const handleGenerate = async (e) => {
    e.preventDefault();
    setError("");
    setQuestions([]);
    setRawAnswer("");
    setAnswers({});
    setSubmitted(false);
    setMeta(null);

    const trimmedEmail = email.trim();
    if (!trimmedEmail) {
      setError("Enter your student email so the local mock exam can use your uploaded documents.");
      return;
    }
    localStorage.setItem("student_email", trimmedEmail);
    window.dispatchEvent(new Event("studyai-identity-changed"));

    const n = Math.min(12, Math.max(3, Number(count) || 5));
    setLoading(true);
    try {
      const geminiPrompt = [
        `Create a short mock exam with ${n} multiple-choice questions on: ${topic.trim() || "general revision"}.`,
        "Return ONLY valid JSON:",
        '{"questions":[{"question":"...","options":["A) ...","B) ...","C) ...","D) ..."],"answer":"B) ...","explanation":"..."}]}',
        "Each question must include 4 options and one correct answer string matching an option.",
      ].join("\n");
      const data = await generateHubContent({
        tool: "mock_exam",
        email: trimmedEmail,
        topic: topic.trim() || undefined,
        count: n,
        geminiConfigured: Boolean(status?.configured),
        geminiPrompt: topic.trim() ? geminiPrompt : undefined,
      });
      if (data.mode === "local" && Array.isArray(data.questions)) {
        const normalized = normalizeExam({ questions: data.questions });
        if (!normalized) {
          setError("Local mock exam did not produce enough multiple-choice questions.");
          return;
        }
        setQuestions(normalized);
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
      const normalized = normalizeExam(parsed);
      if (!normalized) {
        setError(
          "Gemini responded, but mock-exam JSON could not be parsed (need ≥3 MCQs). The raw answer is shown below."
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

  const handleSubmitExam = (e) => {
    e.preventDefault();
    const unanswered = questions.filter((q) => !answers[q.id]);
    if (unanswered.length > 0) {
      setError(`Answer all questions before submitting (${unanswered.length} remaining).`);
      return;
    }
    setError("");
    setSubmitted(true);
  };

  return (
    <div className="sw-hub-tool page-container">
      <div className="sw-hub-tool-hero">
        <p className="sw-hub-eyebrow">Practice</p>
        <h2>Mock Exams</h2>
        <p>
          Build a short multiple-choice set from terms found in your uploaded notes (local extractive).
          Gemini is optional for topic-only exams. Scores use only the returned answer key.
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
                · <Badge variant="info">Gemini-enhanced optional</Badge>
              </>
            ) : (
              <>
                {" "}
                · <Badge variant="warning">Gemini optional</Badge>
              </>
            )}
          </p>
        )}
      </Card>

      <Card title="Create mock exam">
        <form className="sw-hub-tool-form" onSubmit={handleGenerate}>
          <Input
            id="exam-email"
            label="Student email *"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            hint="Required for local document-based mock exams."
            required
          />
          <Textarea
            id="exam-topic"
            label="Topic filter (optional for local)"
            rows={2}
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            placeholder="e.g. Midterm review — Machine Learning fundamentals"
            hint="Filters local extraction; required only for Gemini topic-only fallback."
          />
          <Input
            id="exam-count"
            label="Number of questions"
            type="number"
            min="3"
            max="12"
            value={count}
            onChange={(e) => setCount(e.target.value)}
          />
          {error && !questions.length ? <ErrorMessage message={error} /> : null}
          <Button
            type="submit"
            variant="primary"
            loading={loading}
            disabled={loading || !email.trim()}
          >
            {loading ? "Generating…" : "Generate mock exam"}
          </Button>
        </form>
      </Card>

      {loading ? <Skeleton variant="card" /> : null}

      {!loading && questions.length === 0 && !rawAnswer ? (
        <EmptyState
          title="No exam yet"
          description="Enter your email and upload notes for a local mock exam, or configure Gemini for topic-only generation."
        />
      ) : null}

      {questions.length > 0 ? (
        <form className="sw-hub-exam" onSubmit={handleSubmitExam}>
          {meta ? (
            <div className="sw-hub-tool-meta">
              {meta.provider}
              {meta.model_used ? ` · ${meta.model_used}` : ""}
            </div>
          ) : null}
          {error && questions.length ? <ErrorMessage message={error} /> : null}
          {questions.map((q, idx) => (
            <Card key={q.id} title={`Q${idx + 1}`}>
              <fieldset className="sw-hub-exam-fieldset" disabled={submitted}>
                <legend className="sw-hub-question-prompt">{q.question}</legend>
                <div className="sw-hub-exam-options">
                  {q.options.map((opt) => (
                    <label key={opt} className="sw-hub-exam-option">
                      <input
                        type="radio"
                        name={q.id}
                        value={opt}
                        checked={answers[q.id] === opt}
                        onChange={() =>
                          setAnswers((prev) => ({
                            ...prev,
                            [q.id]: opt,
                          }))
                        }
                      />
                      <span>{opt}</span>
                    </label>
                  ))}
                </div>
              </fieldset>
              {submitted ? (
                <div
                  className={`sw-hub-question-answer${
                    answersMatch(answers[q.id], q.answer)
                      ? " sw-hub-question-answer--ok"
                      : " sw-hub-question-answer--bad"
                  }`}
                >
                  <strong>
                    {answersMatch(answers[q.id], q.answer) ? "Correct" : "Incorrect"}
                  </strong>
                  <div>Your answer: {answers[q.id]}</div>
                  <div>Expected: {q.answer}</div>
                  {q.explanation ? <p>{q.explanation}</p> : null}
                </div>
              ) : null}
            </Card>
          ))}

          {!submitted ? (
            <Button type="submit" variant="primary">
              Submit exam
            </Button>
          ) : score ? (
            <Card title="Your score">
              <div className="sw-hub-exam-score">
                {score.correct} / {score.total} ({score.percent}%)
              </div>
              <ProgressBar
                value={score.percent}
                label="Mock exam score"
                color={score.percent >= 70 ? "success" : score.percent >= 40 ? "warning" : "danger"}
              />
              <p className="sw-hub-tool-disclaimer">
                This score only compares your choices to the model-provided answer key for this
                generated set. It is practice only — not an official assessment.
              </p>
              <Button
                type="button"
                variant="secondary"
                onClick={() => {
                  setSubmitted(false);
                  setAnswers({});
                }}
              >
                Retry same exam
              </Button>
            </Card>
          ) : null}
        </form>
      ) : null}

      {rawAnswer && questions.length === 0 ? (
        <Card title="Raw generation response">
          <div className="sw-hub-tool-output">{rawAnswer}</div>
        </Card>
      ) : null}
    </div>
  );
}

export default MockExam;
