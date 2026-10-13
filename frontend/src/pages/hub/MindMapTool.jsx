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

function normalizeTree(parsed) {
  if (!parsed || typeof parsed !== "object") return null;
  const rootLabel = String(parsed.topic || parsed.label || parsed.root || "").trim();
  const children = Array.isArray(parsed.children) ? parsed.children : [];
  if (!rootLabel) return null;

  const mapNode = (node, depth = 0) => {
    if (!node || typeof node !== "object") return null;
    const label = String(node.label || node.name || node.topic || "").trim();
    if (!label) return null;
    const kids = Array.isArray(node.children)
      ? node.children.map((c) => mapNode(c, depth + 1)).filter(Boolean)
      : [];
    return { label, children: kids, depth };
  };

  return {
    label: rootLabel,
    children: children.map((c) => mapNode(c, 1)).filter(Boolean),
    depth: 0,
  };
}

function MindNode({ node }) {
  return (
    <li className="sw-hub-mind-node">
      <span className="sw-hub-mind-label">{node.label}</span>
      {node.children?.length ? (
        <ul className="sw-hub-mind-branch">
          {node.children.map((child, idx) => (
            <MindNode key={`${child.label}-${idx}`} node={child} />
          ))}
        </ul>
      ) : null}
    </li>
  );
}

function MindMapTool() {
  const [email, setEmail] = useState(() => localStorage.getItem("student_email") || "");
  const [topic, setTopic] = useState("");
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [tree, setTree] = useState(null);
  const [rawAnswer, setRawAnswer] = useState("");
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
    setTree(null);
    setRawAnswer("");
    setMeta(null);

    if (!topic.trim()) {
      setError("Enter a central topic for the mind map.");
      return;
    }

    const trimmedEmail = email.trim();
    if (trimmedEmail) {
      localStorage.setItem("student_email", trimmedEmail);
      window.dispatchEvent(new Event("studyai-identity-changed"));
    }

    setLoading(true);
    try {
      const question = [
        `Build a hierarchical mind map for the academic topic: ${topic.trim()}.`,
        "Return ONLY valid JSON:",
        '{"topic":"...","children":[{"label":"...","children":[{"label":"...","children":[]}]}]}',
        "Use 3–6 top branches and keep depth reasonable for revision.",
      ].join("\n");
      const data = await askTutor({
        question,
        email: trimmedEmail || undefined,
        subject: topic.trim(),
      });
      setRawAnswer(data.answer || "");
      setMeta({ provider: data.provider, model_used: data.model_used });
      const parsed = parseJsonFromAnswer(data.answer);
      const normalized = normalizeTree(parsed);
      if (!normalized) {
        setError(
          "The tutor responded, but mind-map JSON could not be parsed. The raw answer is shown below."
        );
        return;
      }
      setTree(normalized);
    } catch (err) {
      setError(formatApiError(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="sw-hub-tool page-container">
      <div className="sw-hub-tool-hero">
        <p className="sw-hub-eyebrow">Revise</p>
        <h2>Mind Maps</h2>
        <p>
          Ask the AI Tutor for a concept hierarchy, then render it as an outline map. No static
          fake maps are shown if generation fails.
        </p>
        <div className="sw-hub-tool-links">
          <Link to="/hub" className="sw-btn sw-btn--ghost sw-btn--sm">
            ← Learning Hub
          </Link>
          <Link to="/tutor" className="sw-btn sw-btn--secondary sw-btn--sm">
            AI Tutor
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
            {status.message || "Set GEMINI_API_KEY to generate mind maps."}
          </p>
        )}
      </Card>

      <Card title="Build a map">
        <form className="sw-hub-tool-form" onSubmit={handleGenerate}>
          <Input
            id="mm-email"
            label="Student email (optional)"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          <Textarea
            id="mm-topic"
            label="Central topic *"
            rows={2}
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            placeholder="e.g. TCP/IP networking stack"
            required
          />
          {error ? <ErrorMessage message={error} /> : null}
          <Button
            type="submit"
            variant="primary"
            loading={loading}
            disabled={loading || status?.configured === false}
          >
            {loading ? "Generating…" : "Generate mind map"}
          </Button>
        </form>
      </Card>

      {loading ? <Skeleton variant="card" /> : null}

      {!loading && !tree && !rawAnswer ? (
        <EmptyState
          title="No mind map yet"
          description="Enter a topic and generate when the tutor provider is configured."
        />
      ) : null}

      {tree ? (
        <Card title="Concept map">
          {meta ? (
            <div className="sw-hub-tool-meta">
              {meta.provider}
              {meta.model_used ? ` · ${meta.model_used}` : ""}
            </div>
          ) : null}
          <div className="sw-hub-mind-root" aria-label="Mind map">
            <div className="sw-hub-mind-center">{tree.label}</div>
            <ul className="sw-hub-mind-branch sw-hub-mind-branch--root">
              {tree.children.map((child, idx) => (
                <MindNode key={`${child.label}-${idx}`} node={child} />
              ))}
            </ul>
          </div>
        </Card>
      ) : null}

      {rawAnswer && !tree ? (
        <Card title="Raw tutor response">
          <div className="sw-hub-tool-output">{rawAnswer}</div>
        </Card>
      ) : null}
    </div>
  );
}

export default MindMapTool;
