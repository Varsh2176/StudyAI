import { useState, useEffect } from "react";
import API from "../services/api";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorMessage,
  Input,
  ProgressBar,
  Select,
  Skeleton,
  statusToBadgeVariant,
  subjectColor,
} from "../components/ui";

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

  useEffect(() => {
    if (!email) return undefined;

    let cancelled = false;
    const timer = window.setTimeout(() => {
      if (!cancelled) {
        void fetchDashboard(email);
      }
    }, 0);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
    // Initial hydrate only — email is seeded from localStorage.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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

  const actualHours =
    summary?.actual_study_hours !== undefined && summary?.actual_study_hours !== null
      ? summary.actual_study_hours
      : summary?.total_study_hours !== undefined && summary?.total_study_hours !== null
        ? summary.total_study_hours
        : null;
  const plannedHours =
    summary?.planned_study_hours !== undefined && summary?.planned_study_hours !== null
      ? summary.planned_study_hours
      : null;
  const totalSessions =
    summary?.total_sessions !== undefined && summary?.total_sessions !== null
      ? summary.total_sessions
      : null;
  const sessionsCompleted =
    summary?.sessions_completed !== undefined && summary?.sessions_completed !== null
      ? summary.sessions_completed
      : null;
  const sessionsPartial =
    summary?.sessions_partial !== undefined && summary?.sessions_partial !== null
      ? summary.sessions_partial
      : null;
  const sessionsMissed =
    summary?.sessions_missed !== undefined && summary?.sessions_missed !== null
      ? summary.sessions_missed
      : null;
  const completionRate =
    summary?.completion_rate_percent !== undefined && summary?.completion_rate_percent !== null
      ? summary.completion_rate_percent
      : null;
  const fulfillment =
    pva?.fulfillment_percent !== undefined && pva?.fulfillment_percent !== null
      ? pva.fulfillment_percent
      : null;

  const plannedBarMax = Math.max(
    Number(pva?.planned_minutes) || 0,
    Number(pva?.actual_minutes) || 0,
    1
  );
  const plannedBarWidth =
    pva?.planned_minutes != null
      ? Math.round((Number(pva.planned_minutes) / plannedBarMax) * 100)
      : null;
  const actualBarWidth =
    pva?.actual_minutes != null
      ? Math.round((Number(pva.actual_minutes) / plannedBarMax) * 100)
      : null;

  return (
    <div className="sw-progress-page page-container">
      <div className="sw-progress-hero">
        <section className="sw-progress-intro" aria-labelledby="progress-heading">
          <p className="sw-progress-eyebrow">Performance insights</p>
          <h2 id="progress-heading">Progress tracking</h2>
          <p>
            Record completed, partial, and missed study sessions. Compare planned versus actual
            study time and review subject-wise completion rates for your account.
          </p>
        </section>
      </div>

      <Card title="Load progress" className="sw-progress-load-card">
        <form className="sw-progress-load" onSubmit={handleLoad}>
          <Input
            id="progress-email"
            label="Student email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@college.edu"
            required
            hint="Loads metrics from /performance for this student identity."
          />
          <Button type="submit" variant="secondary" loading={loading} disabled={loading}>
            {loading ? "Loading…" : "Load my progress"}
          </Button>
        </form>
      </Card>

      {message ? (
        <div className="sw-progress-success" role="status">
          {message}
        </div>
      ) : null}

      {error ? (
        <ErrorMessage
          message={typeof error === "string" ? error : "Something went wrong."}
          onRetry={email.trim() ? () => fetchDashboard(email.trim()) : undefined}
          retryLabel="Retry load"
        />
      ) : null}

      {loading && !summary ? (
        <div aria-busy="true" aria-label="Loading progress">
          <Skeleton variant="card" />
          <Skeleton variant="block" />
        </div>
      ) : null}

      {!loading && empty ? (
        <EmptyState
          title="No sessions or quizzes yet"
          description="No sessions or quizzes logged yet for this account. Record a study session below to start tracking planned versus actual hours."
        />
      ) : null}

      {summary ? (
        <section className="sw-progress-overview" aria-labelledby="progress-overview-heading">
          <h3 id="progress-overview-heading" className="sw-progress-section-heading">
            Progress overview
          </h3>
          <div className="sw-progress-stats">
            <Card title="Actual study time" className="sw-progress-stat-card">
              {actualHours !== null ? (
                <div className="sw-progress-stat-value">
                  {actualHours}
                  <span className="sw-progress-stat-muted"> hrs</span>
                </div>
              ) : (
                <p className="sw-progress-stat-na">Not available</p>
              )}
              <div className="sw-progress-stat-muted">
                Planned: {plannedHours !== null ? `${plannedHours} hrs` : "Not available"}
              </div>
            </Card>

            <Card title="Sessions" className="sw-progress-stat-card">
              {totalSessions !== null ? (
                <div className="sw-progress-stat-value">{totalSessions}</div>
              ) : (
                <p className="sw-progress-stat-na">Not available</p>
              )}
              <div className="sw-progress-stat-muted">
                Done {sessionsCompleted !== null ? sessionsCompleted : "—"} · Partial{" "}
                {sessionsPartial !== null ? sessionsPartial : "—"} · Missed{" "}
                {sessionsMissed !== null ? sessionsMissed : "—"}
              </div>
            </Card>

            <Card title="Completion rate" className="sw-progress-stat-card">
              {completionRate !== null ? (
                <>
                  <div className="sw-progress-stat-value">{completionRate}%</div>
                  <ProgressBar
                    value={Math.min(100, Math.max(0, Number(completionRate)))}
                    label="Session completion rate"
                    color={
                      Number(completionRate) < 50
                        ? "danger"
                        : Number(completionRate) < 80
                          ? "warning"
                          : "success"
                    }
                  />
                </>
              ) : (
                <p className="sw-progress-stat-na">Not available</p>
              )}
              <div className="sw-progress-stat-muted">
                Plan fulfillment: {fulfillment !== null ? `${fulfillment}%` : "Not available"}
              </div>
            </Card>

            <Card title="Adaptive planning" className="sw-progress-stat-card sw-progress-adapt-action">
              <Button
                type="button"
                variant="primary"
                loading={adapting}
                disabled={adapting || !email.trim()}
                onClick={handleAdaptPlan}
              >
                {adapting ? "Adapting…" : "Adapt from progress"}
              </Button>
              <p className="sw-progress-stat-muted sw-progress-adapt-hint">
                Uses missed/partial sessions and planned vs actual from your logged progress.
              </p>
            </Card>
          </div>
        </section>
      ) : null}

      {adaptResult ? (
        <Card title="Adaptive adjustments" className="sw-progress-adapt-card">
          {adaptResult.adaptations?.length ? (
            <ul className="sw-progress-adapt-list">
              {adaptResult.adaptations.map((note, i) => (
                <li key={i}>{note}</li>
              ))}
            </ul>
          ) : (
            <p className="sw-progress-stat-muted">
              {adaptResult.message || "Adaptation completed with no detailed notes."}
            </p>
          )}
        </Card>
      ) : null}

      {summary && pva ? (
        <Card title="Planned versus actual" className="sw-progress-pva-card">
          <p className="sw-progress-chart-caption">
            Minutes and hours from logged sessions compared with planned study time.
          </p>
          {(plannedBarWidth !== null || actualBarWidth !== null) ? (
            <div
              className="sw-progress-chart"
              role="img"
              aria-label={`Planned ${pva.planned_minutes ?? "n/a"} minutes versus actual ${pva.actual_minutes ?? "n/a"} minutes`}
            >
              {plannedBarWidth !== null ? (
                <div className="sw-progress-chart-row">
                  <span className="sw-progress-chart-label">Planned</span>
                  <div className="sw-progress-chart-track">
                    <div
                      className="sw-progress-chart-fill sw-progress-chart-fill--planned"
                      style={{ width: `${plannedBarWidth}%` }}
                    />
                  </div>
                  <span className="sw-progress-chart-value">{pva.planned_minutes} min</span>
                </div>
              ) : null}
              {actualBarWidth !== null ? (
                <div className="sw-progress-chart-row">
                  <span className="sw-progress-chart-label">Actual</span>
                  <div className="sw-progress-chart-track">
                    <div
                      className="sw-progress-chart-fill sw-progress-chart-fill--actual"
                      style={{ width: `${actualBarWidth}%` }}
                    />
                  </div>
                  <span className="sw-progress-chart-value">{pva.actual_minutes} min</span>
                </div>
              ) : null}
            </div>
          ) : null}
          <div className="sw-progress-pva">
            {pva.planned_minutes !== undefined && pva.planned_minutes !== null ? (
              <div className="sw-progress-pva-item">
                <span className="sw-progress-stat-muted">Planned minutes</span>
                <strong>{pva.planned_minutes}</strong>
              </div>
            ) : null}
            {pva.actual_minutes !== undefined && pva.actual_minutes !== null ? (
              <div className="sw-progress-pva-item">
                <span className="sw-progress-stat-muted">Actual minutes</span>
                <strong>{pva.actual_minutes}</strong>
              </div>
            ) : null}
            {pva.planned_hours !== undefined && pva.planned_hours !== null ? (
              <div className="sw-progress-pva-item">
                <span className="sw-progress-stat-muted">Planned hours</span>
                <strong>{pva.planned_hours}</strong>
              </div>
            ) : null}
            {pva.actual_hours !== undefined && pva.actual_hours !== null ? (
              <div className="sw-progress-pva-item">
                <span className="sw-progress-stat-muted">Actual hours</span>
                <strong>{pva.actual_hours}</strong>
              </div>
            ) : null}
            {fulfillment !== null ? (
              <div className="sw-progress-pva-item">
                <span className="sw-progress-stat-muted">Fulfillment</span>
                <strong>{fulfillment}%</strong>
              </div>
            ) : null}
          </div>
        </Card>
      ) : null}

      <Card title="Subject-wise progress" className="sw-progress-subjects-card">
        {!summary?.subject_metrics?.length ? (
          <EmptyState
            title="No subject data yet"
            description="Log a session or quiz to populate subject completion rates."
          />
        ) : (
          <div className="sw-progress-subjects">
            {summary.subject_metrics.map((subj, idx) => {
              const colors = subjectColor(subj.subject || `subject-${idx}`);
              const rate =
                subj.completion_rate_percent !== undefined && subj.completion_rate_percent !== null
                  ? Number(subj.completion_rate_percent)
                  : null;
              const actualSubj =
                subj.actual_hours !== undefined && subj.actual_hours !== null
                  ? subj.actual_hours
                  : subj.hours_studied !== undefined && subj.hours_studied !== null
                    ? subj.hours_studied
                    : null;
              const plannedSubj =
                subj.planned_hours !== undefined && subj.planned_hours !== null
                  ? subj.planned_hours
                  : null;
              return (
                <div key={idx} className="sw-progress-subj">
                  <div className="sw-progress-subj-head">
                    <strong style={{ color: colors.solid }}>{subj.subject}</strong>
                    <span className="sw-progress-stat-muted">
                      Actual {actualSubj !== null ? actualSubj : "—"} / Planned{" "}
                      {plannedSubj !== null ? plannedSubj : "—"} hrs
                      {rate !== null && !Number.isNaN(rate) ? ` · Completion ${rate}%` : ""}
                      {subj.average_quiz_score != null
                        ? ` · Quiz ${subj.average_quiz_score}%`
                        : ""}
                    </span>
                  </div>
                  {rate !== null && !Number.isNaN(rate) ? (
                    <ProgressBar
                      value={Math.min(100, Math.max(0, rate))}
                      label={`${subj.subject} completion`}
                      color={rate < 50 ? "danger" : rate < 80 ? "warning" : "success"}
                    />
                  ) : (
                    <p className="sw-progress-stat-muted">Completion rate not available</p>
                  )}
                  <div className="sw-progress-stat-muted sw-progress-subj-meta">
                    {subj.sessions_completed ?? 0} completed · {subj.sessions_partial ?? 0}{" "}
                    partial · {subj.sessions_missed ?? 0} missed
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </Card>

      {summary?.recent_sessions?.length > 0 ? (
        <Card title="Recent sessions">
          <div className="sw-progress-table-wrap">
            <table className="sw-progress-table">
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
                    <td style={{ color: subjectColor(s.subject || "session").solid }}>
                      {s.subject}
                    </td>
                    <td>{s.topic || "—"}</td>
                    <td>
                      <Badge variant={statusToBadgeVariant(s.status)}>{s.status}</Badge>
                    </td>
                    <td>{s.planned_minutes ?? "—"} min</td>
                    <td>{s.actual_minutes ?? 0} min</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      ) : null}

      <div className="sw-progress-forms">
        <Card title="Log study session">
          <form onSubmit={handleLogSession}>
            <Input
              id="sess-subject"
              label="Subject"
              type="text"
              value={sessionForm.subject}
              onChange={(e) => setSessionForm({ ...sessionForm, subject: e.target.value })}
              required
            />
            <Input
              id="sess-topic"
              label="Topic"
              type="text"
              value={sessionForm.topic}
              onChange={(e) => setSessionForm({ ...sessionForm, topic: e.target.value })}
            />
            <Select
              id="sess-status"
              label="Outcome"
              value={sessionForm.status}
              onChange={(e) => {
                const status = e.target.value;
                setSessionForm((prev) => ({
                  ...prev,
                  status,
                  actual_minutes:
                    status === "missed"
                      ? 0
                      : status === "partial"
                        ? Math.max(1, Math.floor(Number(prev.planned_minutes) / 2))
                        : prev.planned_minutes,
                }));
              }}
            >
              {SESSION_STATUSES.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </Select>
            <div className="sw-progress-form-row">
              <Input
                id="sess-planned"
                label="Planned (min)"
                type="number"
                min="1"
                max="600"
                value={sessionForm.planned_minutes}
                onChange={(e) =>
                  setSessionForm({ ...sessionForm, planned_minutes: e.target.value })
                }
                required
              />
              <Input
                id="sess-actual"
                label="Actual (min)"
                type="number"
                min="0"
                max="600"
                value={sessionForm.actual_minutes}
                onChange={(e) =>
                  setSessionForm({ ...sessionForm, actual_minutes: e.target.value })
                }
                disabled={sessionForm.status === "missed"}
                required={sessionForm.status !== "missed"}
              />
            </div>
            <Input
              id="sess-date"
              label="Date"
              type="date"
              value={sessionForm.date}
              onChange={(e) => setSessionForm({ ...sessionForm, date: e.target.value })}
              required
            />
            <Button type="submit" variant="primary" className="sw-progress-form-submit">
              Record study session
            </Button>
          </form>
        </Card>

        <Card title="Record quiz score">
          <form onSubmit={handleLogQuiz}>
            <Input
              id="quiz-subject"
              label="Subject"
              type="text"
              value={quizForm.subject}
              onChange={(e) => setQuizForm({ ...quizForm, subject: e.target.value })}
              required
            />
            <Input
              id="quiz-title"
              label="Quiz title"
              type="text"
              value={quizForm.quiz_title}
              onChange={(e) => setQuizForm({ ...quizForm, quiz_title: e.target.value })}
              required
            />
            <div className="sw-progress-form-row">
              <Input
                id="quiz-score"
                label="Marks scored"
                type="number"
                min="0"
                value={quizForm.score}
                onChange={(e) => setQuizForm({ ...quizForm, score: e.target.value })}
                required
              />
              <Input
                id="quiz-total"
                label="Total marks"
                type="number"
                min="1"
                value={quizForm.total_marks}
                onChange={(e) => setQuizForm({ ...quizForm, total_marks: e.target.value })}
                required
              />
            </div>
            <Input
              id="quiz-date"
              label="Date"
              type="date"
              value={quizForm.date}
              onChange={(e) => setQuizForm({ ...quizForm, date: e.target.value })}
              required
            />
            <Button type="submit" variant="primary" className="sw-progress-form-submit">
              Record quiz score
            </Button>
          </form>
        </Card>
      </div>
    </div>
  );
}

export default ProgressTracking;
