import { useState, useEffect } from "react";
import API from "../services/api";

function AiTutor() {
  const [email, setEmail] = useState("");
  const [file, setFile] = useState(null);
  const [subject, setSubject] = useState("Computer Science");
  const [uploading, setUploading] = useState(false);
  const [uploadMsg, setUploadMsg] = useState("");
  const [uploadError, setUploadError] = useState("");
  const [notes, setNotes] = useState([]);

  // Chat state
  const [question, setQuestion] = useState("");
  const [selectedNoteId, setSelectedNoteId] = useState("");
  const [chatHistory, setChatHistory] = useState([]);
  const [asking, setAsking] = useState(false);

  useEffect(() => {
    const savedEmail = localStorage.getItem("student_email") || "student@example.edu";
    setEmail(savedEmail);
    fetchNotes(savedEmail);
  }, []);

  const fetchNotes = async (studentEmail) => {
    try {
      const res = await API.get(`/ai/notes/${studentEmail}`);
      if (res.data?.notes) {
        setNotes(res.data.notes);
        if (res.data.notes.length > 0 && !selectedNoteId) {
          setSelectedNoteId(res.data.notes[0].note_id);
        }
      }
    } catch (err) {
      console.log("Error loading notes:", err);
    }
  };

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
    }
  };

  const handleUpload = async (e) => {
    e.preventDefault();
    if (!file) {
      setUploadError("Please select a PDF or TXT file to upload.");
      return;
    }

    setUploadError("");
    setUploadMsg("");
    setUploading(true);

    const formData = new FormData();
    formData.append("file", file);
    formData.append("email", email);
    formData.append("subject", subject);

    try {
      const res = await API.post("/ai/notes/upload", formData, {
        headers: { "Content-Type": "multipart/form-data" }
      });
      setUploadMsg(`Successfully processed ${res.data.filename} (${res.data.total_pages} pages, ${res.data.total_chunks} chunks).`);
      setFile(null);
      fetchNotes(email);
      if (res.data.note_id) {
        setSelectedNoteId(res.data.note_id);
      }
    } catch (err) {
      console.error(err);
      setUploadError(err.response?.data?.detail || "Failed to upload note.");
    } finally {
      setUploading(false);
    }
  };

  const handleAsk = async (e) => {
    e.preventDefault();
    if (!question.trim()) return;

    const currentQuery = question.trim();
    setQuestion("");
    setAsking(true);

    // Append student question immediately
    setChatHistory((prev) => [
      ...prev,
      { role: "user", text: currentQuery }
    ]);

    try {
      const res = await API.post("/ai/ask", {
        email: email,
        question: currentQuery,
        note_id: selectedNoteId || undefined,
        subject: subject
      });

      setChatHistory((prev) => [
        ...prev,
        {
          role: "ai",
          text: res.data.answer,
          citations: res.data.citations || [],
          grounded: res.data.grounded,
          source: res.data.source
        }
      ]);
    } catch (err) {
      setChatHistory((prev) => [
        ...prev,
        {
          role: "ai",
          text: "An error occurred while communicating with the AI Tutor service. Please ensure the backend server is active.",
          citations: []
        }
      ]);
    } finally {
      setAsking(false);
    }
  };

  return (
    <div className="page-container">
      <div className="page-header">
        <h1>AI Study Tutor & Grounded Notes RAG</h1>
        <p>
          Upload your course lecture notes or textbooks (PDF / TXT). The AI tutor extracts, chunks,
          and retrieves passages to provide answers strictly grounded in your materials with citations.
        </p>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1.6fr", gap: "2rem" }}>
        {/* Left Column: Upload and Notes Management */}
        <div>
          <div className="card">
            <h2 className="card-title">Upload Study Notes</h2>
            {uploadError && <div className="alert alert-danger">{uploadError}</div>}
            {uploadMsg && <div className="alert alert-success">{uploadMsg}</div>}

            <form onSubmit={handleUpload}>
              <div className="form-group" style={{ marginBottom: "1rem" }}>
                <label>Subject / Topic Tag</label>
                <input
                  type="text"
                  placeholder="e.g. Operating Systems"
                  value={subject}
                  onChange={(e) => setSubject(e.target.value)}
                  required
                />
              </div>

              <div className="form-group" style={{ marginBottom: "1.25rem" }}>
                <label>Select Document (.pdf, .txt)</label>
                <input
                  type="file"
                  accept=".pdf,.txt"
                  onChange={handleFileChange}
                  required
                />
                <span className="form-help">Max size: 20MB. Text will be chunked into indexed passages.</span>
              </div>

              <button type="submit" className="btn btn-primary" style={{ width: "100%" }} disabled={uploading}>
                {uploading ? "Extracting & Indexing Notes..." : "Upload & Process Note"}
              </button>
            </form>
          </div>

          <div className="card">
            <h2 className="card-title">Indexed Notes Library</h2>
            {notes.length === 0 ? (
              <p style={{ color: "var(--text-muted)", fontSize: "0.9rem" }}>
                No notes uploaded yet. Upload a lecture PDF above to begin asking questions.
              </p>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                {notes.map((n) => (
                  <div
                    key={n.note_id}
                    onClick={() => setSelectedNoteId(n.note_id)}
                    style={{
                      padding: "0.85rem",
                      borderRadius: "6px",
                      border: selectedNoteId === n.note_id ? "2px solid var(--primary)" : "1px solid var(--border)",
                      background: selectedNoteId === n.note_id ? "var(--primary-light)" : "#fff",
                      cursor: "pointer",
                      textAlign: "left"
                    }}
                  >
                    <div style={{ fontWeight: 600, fontSize: "0.95rem", color: "#1e293b" }}>
                      📄 {n.filename}
                    </div>
                    <div style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginTop: "0.25rem" }}>
                      {n.subject} • {n.total_pages} page(s) • {n.total_chunks} chunks
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Right Column: Grounded AI Tutor Q&A */}
        <div>
          <div className="card" style={{ display: "flex", flexDirection: "column", minHeight: "560px" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
              <h2 className="card-title" style={{ margin: 0 }}>Grounded Tutor Chat</h2>
              <span className="badge badge-info">Strict RAG Grounding</span>
            </div>

            <div className="chat-window" style={{ flex: 1, minHeight: "360px" }}>
              {chatHistory.length === 0 ? (
                <div style={{ textAlign: "center", color: "var(--text-muted)", margin: "auto" }}>
                  <div style={{ fontSize: "2.5rem", marginBottom: "0.5rem" }}>📖</div>
                  <p>Ask a question about your uploaded notes.</p>
                  <p style={{ fontSize: "0.85rem", marginTop: "0.35rem" }}>
                    Answers cite exact page numbers. If something isn't in your notes, the tutor will inform you.
                  </p>
                </div>
              ) : (
                chatHistory.map((msg, i) => (
                  <div
                    key={i}
                    className={`chat-bubble ${msg.role === "user" ? "chat-bubble-user" : "chat-bubble-ai"}`}
                  >
                    <div style={{ whiteSpace: "pre-wrap" }}>{msg.text}</div>

                    {msg.citations?.length > 0 && (
                      <div style={{ marginTop: "0.75rem", borderTop: "1px dashed var(--border)", paddingTop: "0.5rem" }}>
                        <span style={{ fontSize: "0.75rem", fontWeight: 600, color: "#64748b" }}>Citations: </span>
                        {msg.citations.map((c, cIdx) => (
                          <span key={cIdx} className="badge badge-info" style={{ marginRight: "0.4rem", fontSize: "0.75rem" }}>
                            Page {c.page} (Match: {Math.round((c.similarity || 0) * 100)}%)
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                ))
              )}
              {asking && (
                <div className="chat-bubble chat-bubble-ai" style={{ fontStyle: "italic", color: "var(--text-muted)" }}>
                  Retrieving relevant passages and synthesizing grounded answer...
                </div>
              )}
            </div>

            <form onSubmit={handleAsk} style={{ display: "flex", gap: "0.75rem", marginTop: "1rem" }}>
              <input
                type="text"
                placeholder="Ask a question about your study notes..."
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                style={{ flex: 1, padding: "0.75rem 1rem", border: "1px solid var(--border)", borderRadius: "6px" }}
                disabled={asking}
              />
              <button type="submit" className="btn btn-primary" disabled={asking || !question.trim()}>
                {asking ? "Thinking..." : "Ask Tutor"}
              </button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}

export default AiTutor;
