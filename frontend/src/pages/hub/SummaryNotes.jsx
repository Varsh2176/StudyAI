import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorMessage,
  Input,
  Select,
  Skeleton,
  Textarea,
} from "../../components/ui";
import {
  askDocumentRag,
  askTutor,
  fetchTutorStatus,
  formatApiError,
  listDocuments,
} from "../../utils/hubAi";

function SummaryNotes() {
  const [email, setEmail] = useState(() => localStorage.getItem("student_email") || "");
  const [topic, setTopic] = useState("");
  const [sourceMode, setSourceMode] = useState("topic");
  const [documents, setDocuments] = useState([]);
  const [documentId, setDocumentId] = useState("");
  const [status, setStatus] = useState(null);
  const [loadingDocs, setLoadingDocs] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);

  useEffect(() => {
    let cancelled = false;
    void fetchTutorStatus()
      .then((data) => {
        if (!cancelled) setStatus(data);
      })
      .catch(() => {
        if (!cancelled) {
          setStatus({
            configured: false,
            message: "Could not reach /ai/tutor/status. Is the backend running?",
          });
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    const trimmed = email.trim();
    if (!trimmed) {
      return undefined;
    }
    let cancelled = false;
    void (async () => {
      await Promise.resolve();
      if (cancelled) return;
      setLoadingDocs(true);
      try {
        const docs = await listDocuments(trimmed);
        if (!cancelled) setDocuments(docs);
      } catch {
        if (!cancelled) setDocuments([]);
      } finally {
        if (!cancelled) setLoadingDocs(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [email]);

  const docsForEmail = email.trim() ? documents : [];
  const indexedDocs = docsForEmail.filter(
    (d) => String(d.rag_status || "").toLowerCase() === "indexed"
  );

  const handleGenerate = async (e) => {
    e.preventDefault();
    setError("");
    setResult(null);

    const trimmedEmail = email.trim();
    if (trimmedEmail) {
      localStorage.setItem("student_email", trimmedEmail);
      window.dispatchEvent(new Event("studyai-identity-changed"));
    }

    setLoading(true);
    try {
      if (sourceMode === "notes") {
        if (!trimmedEmail) {
          setError("Enter your student email to summarize indexed notes.");
          return;
        }
        if (indexedDocs.length === 0) {
          setError(
            "No indexed PDFs found for this email. Upload and Index a document on Documents first."
          );
          return;
        }
        const question = topic.trim()
          ? `Summarize the key ideas from my notes about: ${topic.trim()}. Use short bullet points and keep claims grounded in the retrieved passages.`
          : "Create a concise study summary of the retrieved notes with clear bullet points for key concepts, definitions, and takeaways.";
        const data = await askDocumentRag({
          email: trimmedEmail,
          question,
          documentId: documentId || undefined,
        });
        setResult({
          kind: "rag",
          text: data.answer,
          mode: data.mode,
          provider: data.provider,
          model_used: data.model_used,
          sources: data.sources || [],
        });
      } else {
        if (!topic.trim()) {
          setError("Enter a topic to summarize.");
          return;
        }
        const question = [
          "Write concise study summary notes for a college student.",
          `Topic: ${topic.trim()}`,
          "Use short sections with bullet points for: Overview, Key concepts, Common mistakes, Quick revision checklist.",
          "Do not invent citations or claim you read a specific PDF.",
        ].join("\n");
        const data = await askTutor({
          question,
          email: trimmedEmail || undefined,
          subject: topic.trim(),
        });
        setResult({
          kind: "tutor",
          text: data.answer,
          provider: data.provider,
          model_used: data.model_used,
          disclaimer: data.disclaimer,
        });
      }
    } catch (err) {
      setError(formatApiError(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="sw-hub-tool page-container">
      <div className="sw-hub-tool-hero">
        <p className="sw-hub-eyebrow">Learn</p>
        <h2>Summary Notes</h2>
        <p>
          Generate study summaries from a topic via the AI Tutor, or from your indexed PDFs via
          Documents RAG. Results come from the live API — nothing is invented client-side.
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

      <Card title="Provider status" className="sw-hub-tool-status">
        {status == null ? (
          <Skeleton variant="line" />
        ) : status.configured ? (
          <p className="sw-hub-tool-status-meta">
            <Badge variant="success">Tutor ready</Badge> {status.provider}
            {status.model ? ` · ${status.model}` : ""}
          </p>
        ) : (
          <p className="sw-hub-tool-status-meta">
            <Badge variant="warning">Tutor may be unavailable</Badge>{" "}
            {status.message || "Set GEMINI_API_KEY for topic summaries."} Notes RAG can still return
            retrieval-only excerpts when documents are indexed.
          </p>
        )}
      </Card>

      <Card title="Create a summary">
        <form className="sw-hub-tool-form" onSubmit={handleGenerate}>
          <Input
            id="summary-email"
            label="Student email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="student@example.edu"
            hint="Required for notes-based summaries; optional profile context for topic mode."
          />
          <Select
            id="summary-source"
            label="Summary source"
            value={sourceMode}
            onChange={(e) => setSourceMode(e.target.value)}
          >
            <option value="topic">Topic (AI Tutor)</option>
            <option value="notes">Indexed notes (Documents RAG)</option>
          </Select>
          {sourceMode === "notes" ? (
            <Select
              id="summary-doc"
              label="Document scope"
              value={documentId}
              onChange={(e) => setDocumentId(e.target.value)}
              hint={
                loadingDocs
                  ? "Loading documents…"
                  : indexedDocs.length
                    ? `${indexedDocs.length} indexed document(s) available`
                    : "No indexed documents yet — upload & Index on Documents"
              }
            >
              <option value="">All indexed documents</option>
              {docsForEmail.map((doc) => (
                <option key={doc.document_id} value={doc.document_id}>
                  {doc.filename} ({doc.rag_status || "not_indexed"})
                </option>
              ))}
            </Select>
          ) : null}
          <Textarea
            id="summary-topic"
            label={sourceMode === "notes" ? "Focus (optional)" : "Topic *"}
            rows={3}
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            placeholder={
              sourceMode === "notes"
                ? "e.g. gradient descent and learning rate"
                : "e.g. Operating system process scheduling"
            }
            required={sourceMode === "topic"}
          />
          {error ? <ErrorMessage message={error} /> : null}
          <Button type="submit" variant="primary" loading={loading} disabled={loading}>
            {loading ? "Generating…" : "Generate summary"}
          </Button>
        </form>
      </Card>

      {loading ? (
        <div aria-busy="true">
          <Skeleton variant="card" />
          <Skeleton variant="block" />
        </div>
      ) : null}

      {!loading && !result && !error ? (
        <EmptyState
          title="No summary yet"
          description="Choose a source, enter a topic or select indexed notes, then generate."
        />
      ) : null}

      {result ? (
        <Card title="Summary result">
          <div className="sw-hub-tool-meta">
            Source: <strong>{result.kind === "rag" ? "Documents RAG" : "AI Tutor"}</strong>
            {result.mode ? <> · Mode: {result.mode}</> : null}
            {result.provider ? <> · {result.provider}</> : null}
            {result.model_used ? <> · {result.model_used}</> : null}
          </div>
          <div className="sw-hub-tool-output" role="region" aria-label="Generated summary">
            {result.text}
          </div>
          {result.sources?.length > 0 ? (
            <ul className="sw-hub-tool-sources">
              {result.sources.map((src, idx) => (
                <li key={`${src.chunk_id || idx}`}>
                  <strong>{src.filename}</strong>
                  {src.page != null ? <> · Page {src.page}</> : null}
                  {src.snippet ? <div className="sw-hub-tool-snippet">{src.snippet}</div> : null}
                </li>
              ))}
            </ul>
          ) : null}
          {result.disclaimer ? (
            <p className="sw-hub-tool-disclaimer">{result.disclaimer}</p>
          ) : (
            <p className="sw-hub-tool-disclaimer">
              This summary is model- or retrieval-generated and is not a substitute for your course
              materials.
            </p>
          )}
        </Card>
      ) : null}
    </div>
  );
}

export default SummaryNotes;
