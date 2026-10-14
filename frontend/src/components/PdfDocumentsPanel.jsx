import { useCallback, useEffect, useRef, useState } from "react";
import API from "../services/api";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorMessage,
  Input,
  Modal,
  Select,
  Skeleton,
  Textarea,
} from "./ui";

const DEFAULT_MAX_MB = 10;

function formatBytes(bytes) {
  if (bytes === undefined || bytes === null) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

function processingStatusVariant(status) {
  const value = String(status || "").toLowerCase();
  if (value === "processed") return "success";
  if (value === "processed_no_text") return "warning";
  if (value.includes("fail") || value.includes("error")) return "danger";
  if (value.includes("process") || value.includes("pending")) return "info";
  return "neutral";
}

function ragStatusVariant(status) {
  const value = String(status || "not_indexed").toLowerCase();
  if (value === "indexed") return "success";
  if (value === "index_failed" || value.includes("fail")) return "danger";
  if (value === "not_indexable") return "warning";
  if (value.includes("process") || value === "indexing") return "info";
  return "neutral";
}

/**
 * Shared M15 PDF upload / list / delete panel.
 * Uses student email from props or localStorage (same auth convention as the rest of the app).
 */
function PdfDocumentsPanel({ email: emailProp, compact = false, onDocumentsChanged }) {
  const [localEmail, setLocalEmail] = useState(
    () => localStorage.getItem("student_email") || ""
  );
  const email = (emailProp || localEmail || "").trim();
  const [documents, setDocuments] = useState([]);
  const [limits, setLimits] = useState({
    max_upload_mb: DEFAULT_MAX_MB,
    max_upload_bytes: DEFAULT_MAX_MB * 1024 * 1024
  });
  const [subject, setSubject] = useState("General");
  const [selectedFile, setSelectedFile] = useState(null);
  const [dragActive, setDragActive] = useState(false);
  const [loadingList, setLoadingList] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [deletingId, setDeletingId] = useState("");
  const [indexingId, setIndexingId] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [ragDocumentId, setRagDocumentId] = useState("");
  const [ragQuestion, setRagQuestion] = useState("");
  const [ragAsking, setRagAsking] = useState(false);
  const [ragAnswer, setRagAnswer] = useState(null);
  const [ragError, setRagError] = useState("");
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [previewId, setPreviewId] = useState("");
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewData, setPreviewData] = useState(null);
  const [previewError, setPreviewError] = useState("");
  const fileInputRef = useRef(null);

  const loadLimits = useCallback(async () => {
    try {
      const res = await API.get("/documents/limits");
      setLimits(res.data);
    } catch {
      setLimits({
        max_upload_mb: DEFAULT_MAX_MB,
        max_upload_bytes: DEFAULT_MAX_MB * 1024 * 1024
      });
    }
  }, []);

  const loadDocuments = useCallback(async (studentEmail) => {
    const trimmed = (studentEmail || "").trim();
    if (!trimmed) {
      setDocuments([]);
      return;
    }
    setLoadingList(true);
    setError("");
    try {
      const res = await API.get("/documents", { params: { email: trimmed } });
      const docs = res.data?.documents || [];
      setDocuments(docs);
      if (onDocumentsChanged) {
        onDocumentsChanged(docs);
      }
    } catch (err) {
      setDocuments([]);
      setError(err.response?.data?.detail || "Failed to load uploaded documents.");
    } finally {
      setLoadingList(false);
    }
  }, [onDocumentsChanged]);

  useEffect(() => {
    let cancelled = false;
    const timer = window.setTimeout(() => {
      if (!cancelled) {
        void loadLimits();
      }
    }, 0);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [loadLimits]);

  useEffect(() => {
    if (!email) return undefined;
    let cancelled = false;
    const timer = window.setTimeout(() => {
      if (!cancelled) {
        void loadDocuments(email);
      }
    }, 0);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [email, loadDocuments]);

  const validateClientFile = (file) => {
    if (!file) {
      return "Please choose a PDF file.";
    }
    const name = file.name || "";
    if (!name.toLowerCase().endsWith(".pdf")) {
      return "Only PDF files (.pdf) are accepted.";
    }
    const maxBytes = limits.max_upload_bytes || DEFAULT_MAX_MB * 1024 * 1024;
    if (file.size > maxBytes) {
      return `File is too large. Maximum size is ${limits.max_upload_mb || DEFAULT_MAX_MB} MB.`;
    }
    if (file.size === 0) {
      return "The selected file is empty.";
    }
    return "";
  };

  const assignFile = (file) => {
    const validationError = validateClientFile(file);
    setMessage("");
    if (validationError) {
      setSelectedFile(null);
      setError(validationError);
      return;
    }
    setError("");
    setSelectedFile(file);
  };

  const handleFileInput = (e) => {
    const file = e.target.files?.[0];
    if (file) {
      assignFile(file);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragActive(false);
    const file = e.dataTransfer.files?.[0];
    if (file) {
      assignFile(file);
    }
  };

  const handleUpload = async (e) => {
    e.preventDefault();
    if (!email) {
      setError("Enter your student email before uploading.");
      return;
    }
    const validationError = validateClientFile(selectedFile);
    if (validationError) {
      setError(validationError);
      return;
    }

    setUploading(true);
    setError("");
    setMessage("");
    localStorage.setItem("student_email", email);

    const formData = new FormData();
    formData.append("file", selectedFile);
    formData.append("email", email);
    formData.append("subject", subject.trim() || "General");

    try {
      const res = await API.post("/documents/upload", formData, {
        headers: { "Content-Type": "multipart/form-data" },
        timeout: 60000
      });
      setMessage(
        `Uploaded "${res.data.filename}" · ${res.data.status}` +
          (res.data.text_available
            ? ` · ${res.data.page_count} page(s), ${res.data.extracted_characters} characters extracted`
            : ` · ${res.data.extraction_message || "No extractable text"}`)
      );
      setSelectedFile(null);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
      await loadDocuments(email);
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(
        typeof detail === "string"
          ? detail
          : Array.isArray(detail)
            ? detail.map((d) => d.msg || JSON.stringify(d)).join(" ")
            : "Upload failed. Please try again."
      );
    } finally {
      setUploading(false);
    }
  };

  const confirmDelete = async () => {
    const documentId = deleteTarget?.document_id;
    if (!email || !documentId) return;
    setDeletingId(documentId);
    setError("");
    setMessage("");
    setDeleteTarget(null);
    try {
      await API.delete(`/documents/${encodeURIComponent(documentId)}`, {
        params: { email }
      });
      setMessage("Document deleted.");
      if (ragDocumentId === documentId) {
        setRagDocumentId("");
        setRagAnswer(null);
      }
      if (previewId === documentId) {
        setPreviewId("");
        setPreviewData(null);
        setPreviewError("");
      }
      await loadDocuments(email);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to delete document.");
    } finally {
      setDeletingId("");
    }
  };

  const handleIndex = async (documentId) => {
    if (!email || !documentId) return;
    setIndexingId(documentId);
    setError("");
    setMessage("");
    try {
      const res = await API.post(
        `/documents/${encodeURIComponent(documentId)}/index`,
        null,
        { params: { email, force: false } }
      );
      setMessage(res.data.message || "Document indexed for RAG.");
      setRagDocumentId(documentId);
      await loadDocuments(email);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to index document for RAG.");
    } finally {
      setIndexingId("");
    }
  };

  const handlePreview = async (documentId) => {
    if (!email || !documentId) return;
    if (previewId === documentId) {
      setPreviewId("");
      setPreviewData(null);
      setPreviewError("");
      return;
    }
    setPreviewId(documentId);
    setPreviewLoading(true);
    setPreviewError("");
    setPreviewData(null);
    try {
      const res = await API.get(`/documents/${encodeURIComponent(documentId)}/text`, {
        params: { email }
      });
      setPreviewData(res.data);
    } catch (err) {
      setPreviewError(err.response?.data?.detail || "Failed to load extracted text.");
    } finally {
      setPreviewLoading(false);
    }
  };

  const handleAskRag = async (e) => {
    e.preventDefault();
    if (!email) {
      setRagError("Enter your student email before asking about notes.");
      return;
    }
    const question = ragQuestion.trim();
    if (!question) {
      setRagError("Enter a question about your uploaded notes.");
      return;
    }

    setRagAsking(true);
    setRagError("");
    setRagAnswer(null);
    try {
      const res = await API.post(
        "/documents/rag/ask",
        {
          email,
          question,
          document_id: ragDocumentId || undefined,
          top_k: 4
        },
        { timeout: 45000 }
      );
      setRagAnswer(res.data);
    } catch (err) {
      const detail = err.response?.data?.detail;
      setRagError(
        typeof detail === "string"
          ? detail
          : "Failed to ask the notes tutor. Index a document first, then retry."
      );
    } finally {
      setRagAsking(false);
    }
  };

  const maxMb = limits.max_upload_mb || DEFAULT_MAX_MB;

  return (
    <div className={compact ? "sw-pdf-panel sw-pdf-panel-compact" : "sw-pdf-panel"}>
      {!compact ? (
        <div className="sw-pdf-workspace-banner">
          <Badge variant="info">PDF only · Max {maxMb} MB</Badge>
          <span className="sw-pdf-workspace-banner-text">
            Limits come from the documents API when available.
          </span>
        </div>
      ) : (
        <div className="sw-pdf-compact-head">
          <h3>Study materials (PDF)</h3>
          <Badge variant="info">Max {maxMb} MB · PDF only</Badge>
        </div>
      )}

      {message ? (
        <div className="sw-pdf-success" role="status">
          {message}
        </div>
      ) : null}

      {error ? (
        <ErrorMessage
          message={typeof error === "string" ? error : "Something went wrong."}
          onRetry={email ? () => loadDocuments(email) : undefined}
          retryLabel="Retry load"
        />
      ) : null}

      <Card title="Upload PDF" className="sw-pdf-upload-card">
        <form onSubmit={handleUpload} className="sw-pdf-upload-form">
          {!emailProp ? (
            <Input
              id="pdf-email"
              label="Student email"
              type="email"
              value={localEmail}
              onChange={(e) => setLocalEmail(e.target.value)}
              placeholder="student@example.edu"
              required
              hint="Documents are stored against this student identity."
            />
          ) : null}

          <Input
            id="pdf-subject"
            label="Subject / topic tag"
            type="text"
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
            placeholder="e.g. Database Systems"
            maxLength={120}
          />

          <div
            className={`sw-pdf-dropzone${dragActive ? " sw-pdf-dropzone--active" : ""}${selectedFile ? " sw-pdf-dropzone--ready" : ""}`}
            onDragEnter={(e) => {
              e.preventDefault();
              setDragActive(true);
            }}
            onDragOver={(e) => {
              e.preventDefault();
              setDragActive(true);
            }}
            onDragLeave={(e) => {
              e.preventDefault();
              setDragActive(false);
            }}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            role="button"
            tabIndex={0}
            aria-label="Choose a PDF file to upload"
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                fileInputRef.current?.click();
              }
            }}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept="application/pdf,.pdf"
              onChange={handleFileInput}
              className="sw-pdf-file-input"
            />
            <span className="sw-pdf-dropzone-icon" aria-hidden="true">
              PDF
            </span>
            <strong>Drag & drop a PDF here</strong>
            <span className="sw-pdf-dropzone-hint">
              or click to browse · PDF only · max {maxMb} MB
            </span>
            {selectedFile ? (
              <span className="sw-pdf-selected">
                Selected: {selectedFile.name} ({formatBytes(selectedFile.size)})
              </span>
            ) : null}
          </div>

          <div className="sw-pdf-upload-actions">
            <Button
              type="submit"
              variant="primary"
              loading={uploading}
              disabled={uploading || !selectedFile}
            >
              {uploading ? "Uploading & extracting…" : "Upload PDF"}
            </Button>
            <Button
              type="button"
              variant="secondary"
              onClick={() => loadDocuments(email)}
              loading={loadingList}
              disabled={loadingList || !email}
            >
              {loadingList ? "Refreshing…" : "Refresh list"}
            </Button>
          </div>
        </form>
      </Card>

      <h3 className="sw-pdf-section-title">
        Uploaded documents {documents.length > 0 ? `(${documents.length})` : ""}
      </h3>

      {loadingList && documents.length === 0 ? (
        <div aria-busy="true" aria-label="Loading documents">
          <Skeleton variant="card" />
          <Skeleton variant="block" />
        </div>
      ) : documents.length === 0 ? (
        <EmptyState
          title="No PDFs uploaded yet"
          description="Upload a study PDF for this email, then index it and ask grounded questions below."
        />
      ) : (
        <div className="sw-pdf-doc-grid">
          {documents.map((doc) => {
            const ragStatus = doc.rag_status || "not_indexed";
            const isPreviewOpen = previewId === doc.document_id;
            return (
              <div key={doc.document_id} className="sw-pdf-doc-card">
                <div className="sw-pdf-doc-head">
                  <div className="sw-pdf-doc-name">{doc.filename}</div>
                  <div className="sw-pdf-doc-badges">
                    <Badge variant={processingStatusVariant(doc.status)}>{doc.status}</Badge>
                    <Badge variant={ragStatusVariant(ragStatus)}>{ragStatus}</Badge>
                  </div>
                </div>
                <div className="sw-pdf-doc-meta">
                  {doc.subject || "General"}
                  {doc.page_count != null ? ` · ${doc.page_count} page(s)` : ""}
                  {doc.text_available
                    ? ` · ${doc.extracted_characters} chars extracted`
                    : " · Text not available"}
                  {doc.rag_chunk_count ? ` · ${doc.rag_chunk_count} RAG chunks` : ""}
                  {doc.ocr_required ? " · OCR required" : ""}
                  {doc.file_size_bytes != null
                    ? ` · ${formatBytes(doc.file_size_bytes)}`
                    : ""}
                </div>
                <div className="sw-pdf-doc-actions">
                  <Button
                    type="button"
                    variant="secondary"
                    size="sm"
                    onClick={() => handleIndex(doc.document_id)}
                    loading={indexingId === doc.document_id}
                    disabled={!doc.text_available || indexingId === doc.document_id}
                  >
                    {indexingId === doc.document_id ? "Indexing..." : "Index"}
                  </Button>
                  <Button
                    type="button"
                    variant="secondary"
                    size="sm"
                    onClick={() => setRagDocumentId(doc.document_id)}
                  >
                    Ask
                  </Button>
                  {doc.text_available ? (
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => handlePreview(doc.document_id)}
                      loading={isPreviewOpen && previewLoading}
                    >
                      {isPreviewOpen ? "Hide text" : "Preview text"}
                    </Button>
                  ) : null}
                  <Button
                    type="button"
                    variant="danger"
                    size="sm"
                    onClick={() => setDeleteTarget(doc)}
                    disabled={deletingId === doc.document_id}
                    loading={deletingId === doc.document_id}
                  >
                    Delete
                  </Button>
                </div>
                {isPreviewOpen ? (
                  <div>
                    {previewLoading ? (
                      <Skeleton variant="block" />
                    ) : previewError ? (
                      <ErrorMessage
                        message={previewError}
                        onRetry={() => handlePreview(doc.document_id)}
                        retryLabel="Retry preview"
                      />
                    ) : previewData?.text_available && previewData?.pages?.length ? (
                      <div className="sw-pdf-preview" aria-label="Extracted text preview">
                        {previewData.pages.slice(0, 3).map((page, idx) => (
                          <div key={page.page ?? idx} className="sw-pdf-preview-page">
                            <strong>Page {page.page ?? idx + 1}</strong>
                            {(page.text || "").slice(0, 600)}
                            {(page.text || "").length > 600 ? "…" : ""}
                          </div>
                        ))}
                        {previewData.pages.length > 3 ? (
                          <div className="sw-pdf-doc-meta">
                            Showing first 3 of {previewData.pages.length} pages from the API.
                          </div>
                        ) : null}
                      </div>
                    ) : (
                      <p className="sw-pdf-doc-meta">
                        {previewData?.ocr_required
                          ? "No extractable text (OCR required)."
                          : "No extracted text returned for this document."}
                      </p>
                    )}
                  </div>
                ) : null}
              </div>
            );
          })}
        </div>
      )}

      <Card title="Ask your notes (RAG)" className="sw-pdf-rag-card" id="ask-notes">
        <p className="sw-pdf-rag-hint">
          Answers are grounded in indexed PDF chunks with page citations. Without GEMINI_API_KEY,
          the API returns a clearly labelled retrieval-only excerpt — never a fabricated success
          answer.
        </p>

        <form onSubmit={handleAskRag} className="sw-pdf-rag-form">
          <Select
            id="rag-doc"
            label="Document scope"
            value={ragDocumentId}
            onChange={(e) => setRagDocumentId(e.target.value)}
            hint="Index a document first, then ask about it or all indexed notes."
          >
            <option value="">All indexed documents for this email</option>
            {documents.map((doc) => (
              <option key={doc.document_id} value={doc.document_id}>
                {doc.filename} ({doc.rag_status || "not_indexed"})
              </option>
            ))}
          </Select>

          <Textarea
            id="rag-question"
            label="Question about your notes"
            rows={3}
            value={ragQuestion}
            onChange={(e) => setRagQuestion(e.target.value)}
            placeholder="e.g. What does my notes say about gradient descent?"
            disabled={ragAsking}
          />

          {ragError ? (
            <ErrorMessage
              message={ragError}
              onRetry={!ragAsking && ragQuestion.trim() ? () => handleAskRag({ preventDefault() {} }) : undefined}
              retryLabel="Retry question"
            />
          ) : null}

          <Button
            type="submit"
            variant="primary"
            className="sw-pdf-rag-submit"
            loading={ragAsking}
            disabled={ragAsking || !ragQuestion.trim()}
          >
            {ragAsking ? "Searching notes…" : "Ask notes tutor"}
          </Button>
        </form>

        {ragAnswer ? (
          <div className="sw-pdf-rag-result">
            <div className="sw-pdf-rag-meta">
              Mode: <strong>{ragAnswer.mode}</strong>
              {ragAnswer.provider ? <> · Provider: {ragAnswer.provider}</> : null}
              {ragAnswer.model_used ? <> · Model: {ragAnswer.model_used}</> : null}
              {ragAnswer.retrieved_count != null ? (
                <> · Retrieved: {ragAnswer.retrieved_count}</>
              ) : null}
            </div>
            <div className="sw-pdf-answer" role="region" aria-label="Notes tutor answer">
              {ragAnswer.answer}
            </div>

            {ragAnswer.sources?.length > 0 ? (
              <ul className="sw-pdf-sources">
                {ragAnswer.sources.map((src, idx) => (
                  <li key={`${src.chunk_id}-${idx}`} className="sw-pdf-source">
                    <strong>{src.filename}</strong>
                    {src.page != null ? <> · Page {src.page}</> : null}
                    {src.similarity_score != null ? <> · score {src.similarity_score}</> : null}
                    {src.snippet ? (
                      <div className="sw-pdf-source-snippet">{src.snippet}</div>
                    ) : null}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="sw-pdf-doc-meta sw-pdf-no-sources">
                No source passages were returned for this question.
              </p>
            )}
          </div>
        ) : null}
      </Card>

      <Modal
        open={Boolean(deleteTarget)}
        title="Delete document?"
        onClose={() => setDeleteTarget(null)}
        footer={
          <>
            <Button type="button" variant="secondary" onClick={() => setDeleteTarget(null)}>
              Cancel
            </Button>
            <Button type="button" variant="danger" onClick={confirmDelete}>
              Delete permanently
            </Button>
          </>
        }
      >
        <p>
          This will permanently delete{" "}
          <strong>{deleteTarget?.filename || "this document"}</strong> and its RAG index for your
          account. This cannot be undone.
        </p>
      </Modal>
    </div>
  );
}

export default PdfDocumentsPanel;
