import { useState, useEffect } from "react";
import API from "../services/api";

function ProgressTracking() {
  const [email, setEmail] = useState("");
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  // Session log state
  const [sessionForm, setSessionForm] = useState({
    subject: "Machine Learning",
    topic: "Linear Models & Regularization",
    duration_minutes: 50
  });

  // Quiz log state
  const [quizForm, setQuizForm] = useState({
    subject: "Machine Learning",
    quiz_title: "Week 3 Practice Quiz",
    score: 82,
    total_marks: 100
  });

  const [adapting, setAdapting] = useState(false);
  const [adaptResult, setAdaptResult] = useState(null);

  useEffect(() => {
    const savedEmail = localStorage.getItem("student_email");
    if (savedEmail) {
      setEmail(savedEmail);
      fetchDashboard(savedEmail);
    }
  }, []);

  const fetchDashboard = async (studentEmail) => {
    setLoading(true);
    try {
      const res = await API.get(`/performance/${studentEmail}`);
      setSummary(res.data);
    } catch (err) {
      console.log("Error loading performance:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleLogSession = async (e) => {
    e.preventDefault();
    setMessage("");
    setError("");

    try {
      await API.post("/performance/session", {
        email,
        subject: sessionForm.subject,
        topic: sessionForm.topic,
        duration_minutes: Number(sessionForm.duration_minutes),
        completed: true
      });
      setMessage("Study session logged successfully!");
      fetchDashboard(email);
    } catch (err) {
      setError("Failed to log study session.");
    }
  };

  const handleLogQuiz = async (e) => {
    e.preventDefault();
    setMessage("");
    setError("");

    try {
      await API.post("/performance/quiz", {
        email,
        subject: quizForm.subject,
        quiz_title: quizForm.quiz_title,
        score: Number(quizForm.score),
        total_marks: Number(quizForm.total_marks)
      });
      setMessage("Quiz score recorded successfully!");
      fetchDashboard(email);
    } catch (err) {
      setError("Failed to record quiz.");
    }
  };

  const handleAdaptPlan = async () => {
    setAdapting(true);
    setAdaptResult(null);
    setMessage("");
    setError("");

    try {
      const res = await API.post("/performance/adapt-plan", { email });
      setAdaptResult(res.data);
      setMessage("Study plan successfully adapted!");
    } catch (err) {
      setError(err.response?.data?.detail || "Could not adapt plan. Please generate a base plan in the Planner first.");
    } finally {
      setAdapting(false);
    }
  };

  return (
    <div className="page-container">
      <div className="page-header">
        <h1>Progress Tracking & Adaptive Plans</h1>
        <p>
          Monitor completed study hours, quiz mastery, and dynamically adapt future timetable allocations
          based on ongoing performance outcomes.
        </p>
      </div>

      {message && <div className="alert alert-success">{message}</div>}
      {error && <div className="alert alert-danger">{error}</div>}

      {/* Aggregate Stats Cards */}
      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-card-title">Total Study Time</div>
          <div className="stat-card-value">
            {summary?.total_study_hours || 0} <span style={{ fontSize: "1rem", color: "var(--text-muted)" }}>hrs</span>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-card-title">Sessions Completed</div>
          <div className="stat-card-value">{summary?.total_completed_sessions || 0}</div>
        </div>

        <div className="stat-card">
          <div className="stat-card-title">Average Quiz Score</div>
          <div className="stat-card-value">
            {summary?.overall_average_quiz_score ? `${summary.overall_average_quiz_score}%` : "N/A"}
          </div>
        </div>

        <div className="stat-card" style={{ display: "flex", flexDirection: "column", justifyContent: "center" }}>
          <button
            type="button"
            className="btn btn-primary"
            onClick={handleAdaptPlan}
            disabled={adapting}
          >
            {adapting ? "Adapting..." : "⚡ Adapt Study Schedule"}
          </button>
          <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: "0.4rem", textAlign: "center" }}>
            Re-balances weak subjects (&lt;70%)
          </span>
        </div>
      </div>

      {/* Adapt Result Banner */}
      {adaptResult && (
        <div className="card" style={{ borderLeft: "4px solid var(--accent)", background: "#faf5ff" }}>
          <h3 style={{ margin: "0 0 0.5rem 0", color: "#581c87" }}>Adaptive Adjustments Made</h3>
          <ul style={{ margin: 0, paddingLeft: "1.25rem", color: "#6b21a8" }}>
            {adaptResult.adaptations?.map((note, i) => (
              <li key={i}>{note}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Subject Mastery and Charts */}
      <div className="card">
        <h2 className="card-title">Subject-wise Mastery & Study Allocation</h2>
        {summary?.subject_metrics?.length === 0 ? (
          <p style={{ color: "var(--text-muted)", fontSize: "0.9rem" }}>
            No subject data logged yet. Record a study session or quiz below to generate analytics.
          </p>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
            {summary?.subject_metrics?.map((subj, idx) => (
              <div key={idx} style={{ background: "#f8fafc", padding: "1rem", borderRadius: "8px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.5rem" }}>
                  <strong>{subj.subject}</strong>
                  <span style={{ fontSize: "0.9rem", color: "var(--text-muted)" }}>
                    Study Time: <strong>{subj.hours_studied} hrs</strong> | Quiz Avg:{" "}
                    <strong>{subj.average_quiz_score ? `${subj.average_quiz_score}%` : "No quiz yet"}</strong>
                  </span>
                </div>

                <div className="progress-bar-container">
                  <div
                    className="progress-bar-fill"
                    style={{
                      width: `${Math.min(100, subj.average_quiz_score || 50)}%`,
                      backgroundColor:
                        (subj.average_quiz_score || 0) < 70
                          ? "var(--danger)"
                          : (subj.average_quiz_score || 0) < 85
                          ? "var(--warning)"
                          : "var(--success)"
                    }}
                  ></div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Logging Forms Grid */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "2rem" }}>
        {/* Log Study Session */}
        <div className="card">
          <h2 className="card-title">Log Completed Study Session</h2>
          <form onSubmit={handleLogSession}>
            <div className="form-group" style={{ marginBottom: "1rem" }}>
              <label>Subject</label>
              <input
                type="text"
                value={sessionForm.subject}
                onChange={(e) => setSessionForm({ ...sessionForm, subject: e.target.value })}
                required
              />
            </div>

            <div className="form-group" style={{ marginBottom: "1rem" }}>
              <label>Topic Covered</label>
              <input
                type="text"
                value={sessionForm.topic}
                onChange={(e) => setSessionForm({ ...sessionForm, topic: e.target.value })}
                required
              />
            </div>

            <div className="form-group" style={{ marginBottom: "1.25rem" }}>
              <label>Duration (Minutes)</label>
              <input
                type="number"
                min="10"
                max="360"
                value={sessionForm.duration_minutes}
                onChange={(e) => setSessionForm({ ...sessionForm, duration_minutes: e.target.value })}
                required
              />
            </div>

            <button type="submit" className="btn btn-primary" style={{ width: "100%" }}>
              Record Study Session
            </button>
          </form>
        </div>

        {/* Log Quiz Result */}
        <div className="card">
          <h2 className="card-title">Record Quiz Score</h2>
          <form onSubmit={handleLogQuiz}>
            <div className="form-group" style={{ marginBottom: "1rem" }}>
              <label>Subject</label>
              <input
                type="text"
                value={quizForm.subject}
                onChange={(e) => setQuizForm({ ...quizForm, subject: e.target.value })}
                required
              />
            </div>

            <div className="form-group" style={{ marginBottom: "1rem" }}>
              <label>Quiz Title</label>
              <input
                type="text"
                value={quizForm.quiz_title}
                onChange={(e) => setQuizForm({ ...quizForm, quiz_title: e.target.value })}
                required
              />
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem", marginBottom: "1.25rem" }}>
              <div className="form-group">
                <label>Marks Scored</label>
                <input
                  type="number"
                  min="0"
                  value={quizForm.score}
                  onChange={(e) => setQuizForm({ ...quizForm, score: e.target.value })}
                  required
                />
              </div>

              <div className="form-group">
                <label>Total Marks</label>
                <input
                  type="number"
                  min="1"
                  value={quizForm.total_marks}
                  onChange={(e) => setQuizForm({ ...quizForm, total_marks: e.target.value })}
                  required
                />
              </div>
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
