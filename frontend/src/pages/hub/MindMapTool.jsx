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
    setTree(null);
    setRawAnswer("");
    setMeta(null);

    const trimmedEmail = email.trim();
    if (!trimmedEmail) {
      setError("Enter your student email so the local outline can use your uploaded documents.");
      return;
    }
    localStorage.setItem("student_email", trimmedEmail);
    window.dispatchEvent(new Event("studyai-identity-changed"));

    setLoading(true);
    try {
      const geminiPrompt = [
        `Build a hierarchical mind map for the academic topic: ${topic.trim() || "study outline"}.`,
        "Return ONLY valid JSON:",
        '{"topic":"...","children":[{"label":"...","children":[{"label":"...","children":[]}]}]}',
        "Use 3–6 top branches and keep depth reasonable for revision.",
      ].join("\n");
      const data = await generateHubContent({
        tool: "mindmap",
        email: trimmedEmail,
        topic: topic.trim() || undefined,
        geminiConfigured: Boolean(status?.configured),
        geminiPrompt: topic.trim() ? geminiPrompt : undefined,
      });
      if (data.mode === "local" && data.tree) {
        const normalized = normalizeTree(data.tree);
        if (!normalized) {
          setError("Local outline was returned but could not be rendered.");
          return;
        }
        setTree(normalized);
        setMeta({
          provider: data.provider,
          label: modeBadgeLabel(data.label || data.mode),
          disclaimer: data.disclaimer || data.note,
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
      const normalized = normalizeTree(parsed);
      if (!normalized) {
        setError(
          "Gemini responded, but mind-map JSON could not be parsed. The raw answer is shown below."
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
          Build a rule-based outline from document headings/sentences (local extractive — not semantic
          AI). Gemini is optional for topic-only generation when a topic is provided.
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
            <Badge variant="success">Local available</Badge> heading/sentence outline
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

      <Card title="Build a map">
        <form className="sw-hub-tool-form" onSubmit={handleGenerate}>
          <Input
            id="mm-email"
            label="Student email *"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            hint="Required for local document-based outlines."
            required
          />
          <Textarea
            id="mm-topic"
            label="Central topic (optional for local)"
            rows={2}
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            placeholder="e.g. TCP/IP networking stack"
            hint="Used as outline root / filter; required only for Gemini topic-only fallback."
          />
          {error ? <ErrorMessage message={error} /> : null}
          <Button
            type="submit"
            variant="primary"
            loading={loading}
            disabled={loading || !email.trim()}
          >
            {loading ? "Generating…" : "Generate mind map"}
          </Button>
        </form>
      </Card>

      {loading ? <Skeleton variant="card" /> : null}

      {!loading && !tree && !rawAnswer ? (
        <EmptyState
          title="No mind map yet"
          description="Enter your email (and upload notes) for a local outline, or configure Gemini for topic-only maps."
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
        <Card title="Raw generation response">
          <div className="sw-hub-tool-output">{rawAnswer}</div>
        </Card>
      ) : null}
    </div>
  );
}

export default MindMapTool;
