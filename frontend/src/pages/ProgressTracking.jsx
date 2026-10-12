import { useState, useEffect } from "react";
import API from "../services/api";

const SESSION_STATUSES = [
  { value: "completed", label: "Completed" },
  { value: "partial", label: "Partially completed" },
  { value: "missed", label: "Missed" },
];

function todayIso() {
  return new Date().toISOString().slice(0, 10);
}

function ProgressTracking() {
  const [email, setEmail] = useState(() => localStorage.getItem("student_email") || "");
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const [sessionForm, setSessionForm] = useState({
    subject: "Machine Learning",
    topic: "Linear Models & Regularization",
    status: "completed",
    planned_minutes: 50,
    actual_minutes: 50,
    date: todayIso(),
  });

  const [quizForm, setQuizForm] = useState({
    subject: "Machine Learning",
    quiz_title: "Week 3 Practice Quiz",
    score: 82,
    total_marks: 100,
    date: todayIso(),
  });

  const [adapting, setAdapting] = useState(false);
  const [adaptResult, setAdaptResult] = useState(null);

  useEffect(() => {
    if (email) {
      fetchDashboard(email);
    }
  }, []);

  const fetchDashboard = async (studentEmail) => {
    const trimmed = (studentEmail || "").trim();
    if (!trimmed) {
      setError("Enter your student email to load progress.");
      setSummary(null);
      return;
    }

    setLoading(true);
    setError("");
    try {
      const res = await API.get(`/performance/${encodeURIComponent(trimmed)}`);
      setSummary(res.data);
      localStorage.setItem("student_email", trimmed);
    } catch (err) {
      const detail = err.response?.data?.detail;
      const status = err.response?.status;
      if (status === 503) {
        setError(
          detail ||
            "Progress storage is unavailable because MongoDB is not connected. Check /health/database."
        );
      } else {
        setError(detail || "Failed to load progress summary.");
      }
      setSummary(null);
    } finally {
      setLoading(false);
    }
  };

  const handleLoad = (e) => {
    e.preventDefault();
    setEmail(email.trim());
    fetchDashboard(email.trim());
  };

  const handleLogSession = async (e) => {
    e.preventDefault();
    setMessage("");
    setError("");

    if (!email.trim()) {
      setError("Student email is required to log a session.");
      return;
    }

    const planned = Number(sessionForm.planned_minutes);
    let actual = Number(sessionForm.actual_minutes);
    if (sessionForm.status === "missed") {
      actual = 0;
    }

    try {
      await API.post("/performance/session", {
        email: email.trim(),
        subject: sessionForm.subject.trim(),
        topic: sessionForm.topic.trim(),
        status: sessionForm.status,
        planned_minutes: planned,
        actual_minutes: actual,
        date: sessionForm.date || todayIso(),
      });
      setMessage("Study session logged successfully.");
      fetchDashboard(email.trim());
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(detail || "Failed to log study session.");
    }
  };

  const handleLogQuiz = async (e) => {
    e.preventDefault();
    setMessage("");
    setError("");

    if (!email.trim()) {
      setError("Student email is required to log a quiz.");
      return;
    }

    try {
      await API.post("/performance/quiz", {
        email: email.trim(),
        subject: quizForm.subject.trim(),
        quiz_title: quizForm.quiz_title.trim(),
        score: Number(quizForm.score),
        total_marks: Number(quizForm.total_marks),
        date: quizForm.date || todayIso(),
      });
      setMessage("Quiz score recorded successfully.");
      fetchDashboard(email.trim());
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(detail || "Failed to record quiz.");
    }
  };

  const handleAdaptPlan = async () => {
    setAdapting(true);
    setAdaptResult(null);
    setMessage("");
    setError("");

    try {
      const res = await API.post("/performance/adapt-plan", { email: email.trim() });
      setAdaptResult(res.data);
      if (res.data?.unchanged) {
        setMessage(res.data.message || "Plan unchanged — no new progress since last adaptation.");
      } else {
        setMessage(res.data?.message || "Study plan successfully adapted from progress.");
      }
    } catch (err) {
      const status = err.response?.status;
      const detail = err.response?.data?.detail;
      if (status === 503) {
        setError(detail || "Database unavailable. Check /health/database.");
      } else {
        setError(detail || "Could not adapt plan. Generate a base plan in the Planner first.");
      }
    } finally {
      setAdapting(false);
    }
  };

  const pva = summary?.planned_versus_actual;
  const empty = summary?.empty;

  return (
    <div className="page-container">
      <div className="page-header">
        <h1>Progress Tracking</h1>
        <p>
          Record completed, partial, and missed study sessions. Compare planned versus actual
          study time and review subject-wise completion rates for your account.
        </p>
      </div>

      <form className="card" onSubmit={handleLoad} style={{ marginBottom: "1.25rem" }}>
        <div className="form-group" style={{ marginBottom: "0.75rem" }}>
          <label htmlFor="progress-email">Student email</label>
          <input
            id="progress-email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@college.edu"
            required
          />
        </div>
        <button type="submit" className="btn btn-secondary" disabled={loading}>
          {loading ? "Loading..." : "Load My Progress"}
        </button>
      </form>

      {message && <div className="alert alert-success">{message}</div>}
      {error && <div className="alert alert-danger">{error}</div>}

      {loading && !summary && (
        <p style={{ color: "var(--text-muted)" }}>Loading progress summary...</p>
      )}

      {!loading && empty && (
        <div className="alert alert-info">
          No sessions or quizzes logged yet for this account. Record a study session below to
          start tracking planned versus actual hours.
        </div>
      )}

      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-card-title">Actual Study Time</div>
          <div className="stat-card-value">
            {summary?.actual_study_hours ?? summary?.total_study_hours ?? 0}{" "}
            <span style={{ fontSize: "1rem", color: "var(--text-muted)" }}>hrs</span>
          </div>
          <div style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginTop: "0.35rem" }}>
            Planned: {summary?.planned_study_hours ?? 0} hrs
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-card-title">Sessions</div>
          <div className="stat-card-value">{summary?.total_sessions ?? 0}</div>
          <div style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginTop: "0.35rem" }}>
            Done {summary?.sessions_completed ?? 0} · Partial {summary?.sessions_partial ?? 0} ·
            Missed {summary?.sessions_missed ?? 0}
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-card-title">Completion Rate</div>
          <div className="stat-card-value">
            {summary ? `${summary.completion_rate_percent ?? 0}%` : "—"}
          </div>
          <div style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginTop: "0.35rem" }}>
            Plan fulfillment: {pva?.fulfillment_percent ?? 0}%
          </div>
        </div>

        <div className="stat-card" style={{ display: "flex", flexDirection: "column", justifyContent: "center" }}>
          <button
            type="button"
            className="btn btn-primary"
            onClick={handleAdaptPlan}
            disabled={adapting || !email.trim()}
          >
            {adapting ? "Adapting..." : "Adapt from Progress"}
          </button>
          <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: "0.4rem", textAlign: "center" }}>
            Uses missed/partial sessions &amp; planned vs actual (M18)
          </span>
        </div>
      </div>

      {adaptResult && (
        <div className="card" style={{ borderLeft: "4px solid var(--accent)" }}>
          <h3 style={{ margin: "0 0 0.5rem 0" }}>Adaptive Adjustments</h3>
          <ul style={{ margin: 0, paddingLeft: "1.25rem" }}>
            {adaptResult.adaptations?.map((note, i) => (
              <li key={i}>{note}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="card">
        <h2 className="card-title">Subject-wise Progress</h2>
        {!summary?.subject_metrics?.length ? (
          <p style={{ color: "var(--text-muted)", fontSize: "0.9rem" }}>
            No subject data yet. Log a session or quiz to populate this section.
          </p>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
            {summary.subject_metrics.map((subj, idx) => (
              <div key={idx} style={{ background: "var(--bg-muted, #f8fafc)", padding: "1rem", borderRadius: "8px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.5rem", flexWrap: "wrap", gap: "0.5rem" }}>
                  <strong>{subj.subject}</strong>
                  <span style={{ fontSize: "0.9rem", color: "var(--text-muted)" }}>
                    Actual {subj.actual_hours ?? subj.hours_studied ?? 0} / Planned {subj.planned_hours ?? 0} hrs
                    {" · "}
                    Completion {subj.completion_rate_percent ?? 0}%
                    {subj.average_quiz_score != null ? ` · Quiz ${subj.average_quiz_score}%` : ""}
                  </span>
                </div>
                <div className="progress-bar-container">
                  <div
                    className="progress-bar-fill"
                    style={{
                      width: `${Math.min(100, subj.completion_rate_percent || 0)}%`,
                      backgroundColor:
                        (subj.completion_rate_percent || 0) < 50
                          ? "var(--danger)"
                          : (subj.completion_rate_percent || 0) < 80
                          ? "var(--warning)"
                          : "var(--success)",
                    }}
                  />
                </div>
                <div style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginTop: "0.4rem" }}>
                  {subj.sessions_completed ?? 0} completed · {subj.sessions_partial ?? 0} partial ·{" "}
                  {subj.sessions_missed ?? 0} missed
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {summary?.recent_sessions?.length > 0 && (
        <div className="card">
          <h2 className="card-title">Recent Sessions</h2>
          <div className="table-responsive">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Subject</th>
                  <th>Topic</th>
                  <th>Status</th>
                  <th>Planned</th>
                  <th>Actual</th>
                </tr>
              </thead>
              <tbody>
                {summary.recent_sessions.map((s, idx) => (
                  <tr key={s.session_id || idx}>
                    <td>{s.date || "—"}</td>
                    <td>{s.subject}</td>
                    <td>{s.topic || "—"}</td>
                    <td>
                      <span className="badge badge-medium">{s.status}</span>
                    </td>
                    <td>{s.planned_minutes ?? "—"} min</td>
                    <td>{s.actual_minutes ?? 0} min</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "2rem" }}>
        <div className="card">
          <h2 className="card-title">Log Study Session</h2>
          <form onSubmit={handleLogSession}>
            <div className="form-group" style={{ marginBottom: "1rem" }}>
              <label htmlFor="sess-subject">Subject</label>
              <input
                id="sess-subject"
                type="text"
                value={sessionForm.subject}
                onChange={(e) => setSessionForm({ ...sessionForm, subject: e.target.value })}
                required
              />
            </div>

            <div className="form-group" style={{ marginBottom: "1rem" }}>
              <label htmlFor="sess-topic">Topic</label>
              <input
                id="sess-topic"
                type="text"
                value={sessionForm.topic}
                onChange={(e) => setSessionForm({ ...sessionForm, topic: e.target.value })}
              />
            </div>

            <div className="form-group" style={{ marginBottom: "1rem" }}>
              <label htmlFor="sess-status">Outcome</label>
              <select
                id="sess-status"
                value={sessionForm.status}
                onChange={(e) => {
                  const status = e.target.value;
                  setSessionForm((prev) => ({
                    ...prev,
                    status,
                    actual_minutes:
                      status === "missed" ? 0 : status === "partial" ? Math.max(1, Math.floor(Number(prev.planned_minutes) / 2)) : prev.planned_minutes,
                  }));
                }}
              >
                {SESSION_STATUSES.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem", marginBottom: "1rem" }}>
              <div className="form-group">
                <label htmlFor="sess-planned">Planned (min)</label>
                <input
                  id="sess-planned"
                  type="number"
                  min="1"
                  max="600"
                  value={sessionForm.planned_minutes}
                  onChange={(e) => setSessionForm({ ...sessionForm, planned_minutes: e.target.value })}
                  required
                />
              </div>
              <div className="form-group">
                <label htmlFor="sess-actual">Actual (min)</label>
                <input
                  id="sess-actual"
                  type="number"
                  min="0"
                  max="600"
                  value={sessionForm.actual_minutes}
                  onChange={(e) => setSessionForm({ ...sessionForm, actual_minutes: e.target.value })}
                  disabled={sessionForm.status === "missed"}
                  required={sessionForm.status !== "missed"}
                />
              </div>
            </div>

            <div className="form-group" style={{ marginBottom: "1.25rem" }}>
              <label htmlFor="sess-date">Date</label>
              <input
                id="sess-date"
                type="date"
                value={sessionForm.date}
                onChange={(e) => setSessionForm({ ...sessionForm, date: e.target.value })}
                required
              />
            </div>

            <button type="submit" className="btn btn-primary" style={{ width: "100%" }}>
              Record Study Session
            </button>
          </form>
        </div>

        <div className="card">
          <h2 className="card-title">Record Quiz Score</h2>
          <form onSubmit={handleLogQuiz}>
            <div className="form-group" style={{ marginBottom: "1rem" }}>
              <label htmlFor="quiz-subject">Subject</label>
              <input
                id="quiz-subject"
                type="text"
                value={quizForm.subject}
                onChange={(e) => setQuizForm({ ...quizForm, subject: e.target.value })}
                required
              />
            </div>

            <div className="form-group" style={{ marginBottom: "1rem" }}>
              <label htmlFor="quiz-title">Quiz Title</label>
              <input
                id="quiz-title"
                type="text"
                value={quizForm.quiz_title}
                onChange={(e) => setQuizForm({ ...quizForm, quiz_title: e.target.value })}
                required
              />
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem", marginBottom: "1rem" }}>
              <div className="form-group">
                <label htmlFor="quiz-score">Marks Scored</label>
                <input
                  id="quiz-score"
                  type="number"
                  min="0"
                  value={quizForm.score}
                  onChange={(e) => setQuizForm({ ...quizForm, score: e.target.value })}
                  required
                />
              </div>
              <div className="form-group">
                <label htmlFor="quiz-total">Total Marks</label>
                <input
                  id="quiz-total"
                  type="number"
                  min="1"
                  value={quizForm.total_marks}
                  onChange={(e) => setQuizForm({ ...quizForm, total_marks: e.target.value })}
                  required
                />
              </div>
            </div>

            <div className="form-group" style={{ marginBottom: "1.25rem" }}>
              <label htmlFor="quiz-date">Date</label>
              <input
                id="quiz-date"
                type="date"
                value={quizForm.date}
                onChange={(e) => setQuizForm({ ...quizForm, date: e.target.value })}
                required
              />
            </div>

            <button type="submit" className="btn btn-primary" style={{ width: "100%" }}>
              Record Quiz Score
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}

export default ProgressTracking;
