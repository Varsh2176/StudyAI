import { useCallback, useEffect, useRef, useState } from "react";
import API from "../services/api";

const DEFAULT_MAX_MB = 10;

function formatBytes(bytes) {
  if (bytes === undefined || bytes === null) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

function statusBadgeClass(status) {
  if (status === "processed") return "badge-low";
  if (status === "processed_no_text") return "badge-medium";
  return "badge-high";
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
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
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

  const handleDelete = async (documentId) => {
    if (!email || !documentId) return;
    setDeletingId(documentId);
    setError("");
    setMessage("");
    try {
      await API.delete(`/documents/${encodeURIComponent(documentId)}`, {
        params: { email }
      });
      setMessage("Document deleted.");
      await loadDocuments(email);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to delete document.");
    } finally {
      setDeletingId("");
    }
  };

  return (
    <div className={compact ? "pdf-panel pdf-panel-compact" : "pdf-panel"}>
      {!compact && (
        <div className="page-header" style={{ marginBottom: "1.25rem" }}>
          <h1>Study Materials (PDF)</h1>
          <p>
            Upload PDF notes for secure storage and text extraction. Extracted text is saved for future
            note-based tutoring (M16). Maximum size: {limits.max_upload_mb || DEFAULT_MAX_MB} MB.
          </p>
        </div>
      )}

      {compact && (
        <div style={{ display: "flex", justifyContent: "space-between", gap: "1rem", flexWrap: "wrap", marginBottom: "1rem" }}>
          <h2 className="card-title" style={{ margin: 0 }}>Study Materials (PDF)</h2>
          <span className="badge badge-info">Max {limits.max_upload_mb || DEFAULT_MAX_MB} MB · PDF only</span>
        </div>
      )}

      {message && <div className="alert alert-success">{message}</div>}
      {error && (
        <div className="alert alert-danger" style={{ display: "flex", justifyContent: "space-between", gap: "1rem", flexWrap: "wrap", alignItems: "center" }}>
          <span>{error}</span>
          <button type="button" className="btn btn-secondary btn-sm" onClick={() => loadDocuments(email)} disabled={loadingList}>
            Retry
          </button>
        </div>
      )}

      <form onSubmit={handleUpload} className="pdf-upload-form">
        {!emailProp && (
          <div className="form-group" style={{ marginBottom: "1rem" }}>
            <label htmlFor="pdf-email">Student Email *</label>
            <input
              id="pdf-email"
              type="email"
              value={localEmail}
              onChange={(e) => setLocalEmail(e.target.value)}
              placeholder="student@example.edu"
              required
            />
          </div>
        )}

        <div className="form-group" style={{ marginBottom: "1rem" }}>
          <label htmlFor="pdf-subject">Subject / Topic tag</label>
          <input
            id="pdf-subject"
            type="text"
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
            placeholder="e.g. Database Systems"
            maxLength={120}
          />
        </div>

        <div
          className={`pdf-dropzone ${dragActive ? "pdf-dropzone-active" : ""}`}
          onDragEnter={(e) => { e.preventDefault(); setDragActive(true); }}
          onDragOver={(e) => { e.preventDefault(); setDragActive(true); }}
          onDragLeave={(e) => { e.preventDefault(); setDragActive(false); }}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
          role="button"
          tabIndex={0}
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
            style={{ display: "none" }}
          />
          <strong>Drag & drop a PDF here</strong>
          <span style={{ color: "var(--text-muted)", fontSize: "0.9rem" }}>
            or click to browse · PDF only · max {limits.max_upload_mb || DEFAULT_MAX_MB} MB
          </span>
          {selectedFile && (
            <span style={{ marginTop: "0.5rem", fontWeight: 600 }}>
              Selected: {selectedFile.name} ({formatBytes(selectedFile.size)})
            </span>
          )}
        </div>

        <div style={{ display: "flex", gap: "0.75rem", marginTop: "1rem", flexWrap: "wrap" }}>
          <button type="submit" className="btn btn-primary" disabled={uploading || !selectedFile}>
            {uploading ? "Uploading & extracting..." : "Upload PDF"}
          </button>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => loadDocuments(email)}
            disabled={loadingList || !email}
          >
            {loadingList ? "Refreshing..." : "Refresh List"}
          </button>
        </div>
      </form>

      <div style={{ marginTop: "1.75rem" }}>
        <h3 style={{ fontSize: "1.05rem", marginBottom: "0.75rem" }}>
          Uploaded documents {documents.length > 0 ? `(${documents.length})` : ""}
        </h3>

        {loadingList && documents.length === 0 ? (
          <p style={{ color: "var(--text-muted)" }}>Loading documents...</p>
        ) : documents.length === 0 ? (
          <div className="empty-state-inline">
            <p style={{ color: "var(--text-muted)", margin: 0 }}>
              No PDFs uploaded yet for this email. Upload a study PDF to extract text for later RAG (M16).
            </p>
          </div>
        ) : (
          <div className="table-responsive">
            <table className="styled-table">
              <thead>
                <tr>
                  <th>Filename</th>
                  <th>Status</th>
                  <th>Pages</th>
                  <th>Text</th>
                  <th>Size</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {documents.map((doc) => (
                  <tr key={doc.document_id}>
                    <td>
                      <div style={{ fontWeight: 600 }}>{doc.filename}</div>
                      <div style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
                        {doc.subject || "General"}
                        {doc.ocr_required ? " · OCR required (no extractable text)" : ""}
                      </div>
                    </td>
                    <td>
                      <span className={`badge ${statusBadgeClass(doc.status)}`}>{doc.status}</span>
                    </td>
                    <td>{doc.page_count ?? "—"}</td>
                    <td>
                      {doc.text_available
                        ? `${doc.extracted_characters} chars`
                        : "Not available"}
                    </td>
                    <td>{formatBytes(doc.file_size_bytes)}</td>
                    <td>
                      <button
                        type="button"
                        className="btn btn-secondary btn-sm"
                        style={{ color: "var(--danger)" }}
                        onClick={() => handleDelete(doc.document_id)}
                        disabled={deletingId === doc.document_id}
                      >
                        {deletingId === doc.document_id ? "Deleting..." : "Delete"}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

export default PdfDocumentsPanel;
