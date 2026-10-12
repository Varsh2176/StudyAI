import { useState, useEffect, useCallback } from "react";
import { Link } from "react-router-dom";
import API from "../services/api";
import PdfDocumentsPanel from "../components/PdfDocumentsPanel";

function getRiskBadgeClass(level) {
  if (level === "High Risk") return "badge-high";
  if (level === "Moderate Risk" || level === "Medium Risk") return "badge-medium";
  return "badge-low";
}

function Dashboard() {
  const [emailInput, setEmailInput] = useState(
    () => localStorage.getItem("student_email") || ""
  );
  const [email, setEmail] = useState("");
  const [profile, setProfile] = useState(null);
  const [latestPrediction, setLatestPrediction] = useState(null);
  const [studyPlan, setStudyPlan] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [loadNotes, setLoadNotes] = useState([]);
  const [scheduleTab, setScheduleTab] = useState("daily");

  const loadDashboard = useCallback(async (studentEmail) => {
    const trimmed = (studentEmail || "").trim();
    if (!trimmed) {
      setError("Enter the student email used during registration to load your dashboard.");
      setProfile(null);
      setLatestPrediction(null);
      setStudyPlan(null);
      setLoadNotes([]);
      return;
    }

    setLoading(true);
    setError("");
    setLoadNotes([]);
    setEmail(trimmed);
    localStorage.setItem("student_email", trimmed);

    const notes = [];
    let nextProfile = null;
    let nextPrediction = null;
    let nextPlan = null;

    try {
      const [profileRes, predictionRes, planRes] = await Promise.allSettled([
        API.get(`/student/${encodeURIComponent(trimmed)}`),
        API.get(`/predict/history/${encodeURIComponent(trimmed)}`),
        API.get(`/study-plan/${encodeURIComponent(trimmed)}`)
      ]);

      if (profileRes.status === "fulfilled") {
        const data = profileRes.value.data;
        if (data && data.course !== undefined) {
          nextProfile = data;
        } else {
          notes.push("No student profile found yet. Create one on the Profile page.");
        }
      } else {
        notes.push("Could not load student profile from the backend.");
      }

      if (predictionRes.status === "fulfilled") {
        const predictions = predictionRes.value.data?.predictions || [];
        if (predictions.length > 0) {
          nextPrediction = predictions[0];
        } else {
          notes.push("No exam score prediction saved yet. Run a prediction on Predict Score & Risk.");
        }
      } else {
        notes.push("Could not load prediction history from the backend.");
      }

      if (planRes.status === "fulfilled") {
        const plan = planRes.value.data?.plan;
        if (plan) {
          nextPlan = plan;
        } else {
          notes.push("No study plan saved yet. Generate one in the Study Planner.");
        }
      } else {
        notes.push("Could not load the saved study plan from the backend.");
      }

      const allFailed =
        profileRes.status === "rejected" &&
        predictionRes.status === "rejected" &&
        planRes.status === "rejected";

      if (allFailed) {
        const firstErr = profileRes.reason;
        setError(
          firstErr?.response?.data?.detail ||
            firstErr?.message ||
            "Failed to reach the backend. Confirm the API is running on port 8000."
        );
      }

      setProfile(nextProfile);
      setLatestPrediction(nextPrediction);
      setStudyPlan(nextPlan);
      setLoadNotes(notes);
    } catch (err) {
      setError(
        err?.response?.data?.detail ||
          err?.message ||
          "Unexpected error while loading the dashboard."
      );
      setProfile(null);
      setLatestPrediction(null);
      setStudyPlan(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const savedEmail = localStorage.getItem("student_email");
    if (!savedEmail) return undefined;

    let cancelled = false;
    const timer = window.setTimeout(() => {
      if (!cancelled) {
        void loadDashboard(savedEmail);
      }
    }, 0);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [loadDashboard]);

  const handleLoadSubmit = (e) => {
    e.preventDefault();
    loadDashboard(emailInput);
  };

  const predictedScore =
    latestPrediction?.prediction ??
    latestPrediction?.predicted_exam_score ??
    null;

  const riskAssessment =
    latestPrediction?.risk_assessment ||
    studyPlan?.risk_assessment_details ||
    null;

  const riskCategory =
    riskAssessment?.risk_category ||
    riskAssessment?.risk_level ||
    studyPlan?.risk_category_applied ||
    null;

  const recommendedDailyHours =
    studyPlan?.m10_recommended_daily_hours ??
    studyPlan?.m10_recommendation?.recommended_daily_hours ??
    null;

  const recommendedWeeklyHours =
    studyPlan?.m10_recommended_weekly_hours ??
    studyPlan?.m10_recommendation?.recommended_weekly_hours ??
    null;

  const dailySlots = studyPlan?.daily_schedule || studyPlan?.timetable || [];
  const weeklySchedule = studyPlan?.weekly_schedule || {};
  const subjects = Array.isArray(profile?.subjects)
    ? profile.subjects
    : typeof profile?.subjects === "string"
      ? profile.subjects.split(",").map((s) => s.trim()).filter(Boolean)
      : [];

  return (
    <div className="page-container">
      <div className="page-header">
        <h1>Student Dashboard</h1>
        <p>
          Overview of your profile, latest ML prediction, academic risk, recommended study hours,
          and the timetable saved by the study-plan API.
        </p>
      </div>

      <div className="card">
        <form className="dashboard-email-form" onSubmit={handleLoadSubmit}>
          <div className="form-group" style={{ flex: 1, marginBottom: 0 }}>
            <label htmlFor="dashboard-email">Student Email</label>
            <input
              id="dashboard-email"
              type="email"
              placeholder="student@example.edu"
              value={emailInput}
              onChange={(e) => setEmailInput(e.target.value)}
              required
            />
          </div>
          <div className="dashboard-email-actions">
            <button type="submit" className="btn btn-primary" disabled={loading}>
              {loading ? "Loading..." : "Load Dashboard"}
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => loadDashboard(email || emailInput)}
              disabled={loading || !(email || emailInput)}
            >
              Retry
            </button>
          </div>
        </form>
      </div>

      {error && (
        <div className="alert alert-danger" style={{ display: "flex", justifyContent: "space-between", gap: "1rem", alignItems: "center", flexWrap: "wrap" }}>
          <span>{error}</span>
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={() => loadDashboard(email || emailInput)}
            disabled={loading}
          >
            Retry
          </button>
        </div>
      )}

      {loading && (
        <div className="card dashboard-loading">
          <p style={{ margin: 0, color: "var(--text-muted)" }}>Loading your academic overview from the backend...</p>
        </div>
      )}

      {!loading && !email && !error && (
        <div className="card empty-state">
          <h2 className="card-title">No student selected</h2>
          <p style={{ color: "var(--text-muted)", marginBottom: "1rem" }}>
            Register or enter the email you used for your student profile to view real dashboard data.
          </p>
          <Link to="/" className="btn btn-primary">Go to Registration</Link>
        </div>
      )}

      {!loading && email && (
        <>
          {loadNotes.length > 0 && (
            <div className="alert alert-info">
              <ul style={{ margin: 0, paddingLeft: "1.2rem" }}>
                {loadNotes.map((note, idx) => (
                  <li key={idx}>{note}</li>
                ))}
              </ul>
            </div>
          )}

          <div className="stats-grid">
            <div className="stat-card">
              <div className="stat-card-title">Predicted Exam Score</div>
              <div className="stat-card-value">
                {predictedScore !== null && predictedScore !== undefined ? (
                  <>
                    {predictedScore}
                    <span style={{ fontSize: "1rem", color: "var(--text-muted)" }}> / 100</span>
                  </>
                ) : (
                  <span style={{ fontSize: "1.1rem", color: "var(--text-muted)" }}>Not available</span>
                )}
              </div>
              {predictedScore === null && (
                <Link to="/predict" className="btn btn-secondary btn-sm" style={{ marginTop: "0.75rem" }}>
                  Predict Score
                </Link>
              )}
            </div>

            <div className="stat-card">
              <div className="stat-card-title">Academic Risk</div>
              <div className="stat-card-value" style={{ fontSize: "1.35rem" }}>
                {riskCategory ? (
                  <span className={`badge ${getRiskBadgeClass(riskCategory)}`}>{riskCategory}</span>
                ) : (
                  <span style={{ fontSize: "1.1rem", color: "var(--text-muted)" }}>Not available</span>
                )}
              </div>
              {!riskCategory && (
                <Link to="/predict" className="btn btn-secondary btn-sm" style={{ marginTop: "0.75rem" }}>
                  Assess Risk
                </Link>
              )}
            </div>

            <div className="stat-card">
              <div className="stat-card-title">Recommended Study Hours</div>
              <div className="stat-card-value">
                {recommendedDailyHours !== null && recommendedDailyHours !== undefined ? (
                  <>
                    {recommendedDailyHours}
                    <span style={{ fontSize: "1rem", color: "var(--text-muted)" }}> hrs/day</span>
                  </>
                ) : (
                  <span style={{ fontSize: "1.1rem", color: "var(--text-muted)" }}>Not available</span>
                )}
              </div>
              {recommendedWeeklyHours !== null && recommendedWeeklyHours !== undefined && (
                <div style={{ fontSize: "0.85rem", color: "var(--text-muted)", marginTop: "0.35rem" }}>
                  {recommendedWeeklyHours} hrs/week
                </div>
              )}
              {recommendedDailyHours === null && (
                <Link to="/planner" className="btn btn-secondary btn-sm" style={{ marginTop: "0.75rem" }}>
                  Generate Plan
                </Link>
              )}
            </div>

            <div className="stat-card">
              <div className="stat-card-title">Daily Availability</div>
              <div className="stat-card-value">
                {profile?.study_hours !== undefined && profile?.study_hours !== null ? (
                  <>
                    {profile.study_hours}
                    <span style={{ fontSize: "1rem", color: "var(--text-muted)" }}> hrs/day</span>
                  </>
                ) : studyPlan?.daily_available_hours !== undefined ? (
                  <>
                    {studyPlan.daily_available_hours}
                    <span style={{ fontSize: "1rem", color: "var(--text-muted)" }}> hrs/day</span>
                  </>
                ) : (
                  <span style={{ fontSize: "1.1rem", color: "var(--text-muted)" }}>Not available</span>
                )}
              </div>
            </div>
          </div>

          <div className="card">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "1rem", flexWrap: "wrap", marginBottom: "1rem" }}>
              <h2 className="card-title" style={{ margin: 0 }}>Student Profile</h2>
              <Link to="/profile" className="btn btn-secondary btn-sm">
                {profile ? "Edit Profile" : "Create Profile"}
              </Link>
            </div>

            {!profile ? (
              <div className="empty-state-inline">
                <p style={{ color: "var(--text-muted)", margin: 0 }}>
                  No profile data returned for <strong>{email}</strong>. Save a profile to populate this section.
                </p>
              </div>
            ) : (
              <div className="profile-detail-grid">
                <div><span className="detail-label">Email</span><span>{profile.email}</span></div>
                <div><span className="detail-label">Course</span><span>{profile.course}</span></div>
                <div><span className="detail-label">Branch</span><span>{profile.branch}</span></div>
                <div><span className="detail-label">Year</span><span>{profile.year}</span></div>
                <div><span className="detail-label">Age</span><span>{profile.age}</span></div>
                <div><span className="detail-label">Attendance</span><span>{profile.attendance}%</span></div>
                <div><span className="detail-label">Previous CGPA</span><span>{profile.previous_cgpa}</span></div>
                <div><span className="detail-label">Study Hours</span><span>{profile.study_hours} hrs/day</span></div>
                <div className="profile-subjects">
                  <span className="detail-label">Subjects</span>
                  <div className="subject-chip-row">
                    {subjects.length > 0 ? (
                      subjects.map((subject) => (
                        <span key={subject} className="badge badge-info">{subject}</span>
                      ))
                    ) : (
                      <span style={{ color: "var(--text-muted)" }}>None listed</span>
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>

          <div className="card">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "1rem", flexWrap: "wrap", marginBottom: "1rem" }}>
              <h2 className="card-title" style={{ margin: 0 }}>Prediction & Risk Details</h2>
              <Link to="/predict" className="btn btn-secondary btn-sm">Open Predictor</Link>
            </div>

            {!latestPrediction && !riskAssessment ? (
              <p style={{ color: "var(--text-muted)", margin: 0 }}>
                Prediction history is empty for this student. After you run a prediction with your email,
                the latest score and risk assessment appear here.
              </p>
            ) : (
              <div className="dashboard-split">
                <div>
                  <div style={{ fontSize: "0.85rem", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                    Latest Predicted Score
                  </div>
                  <div style={{ fontSize: "2.5rem", fontWeight: 800, color: "var(--primary)", lineHeight: 1.2 }}>
                    {predictedScore !== null && predictedScore !== undefined ? predictedScore : "—"}
                    {predictedScore !== null && predictedScore !== undefined && (
                      <span style={{ fontSize: "1.1rem", color: "var(--text-muted)" }}> / 100</span>
                    )}
                  </div>
                  {predictedScore !== null && predictedScore !== undefined && (
                    <div className="progress-bar-container" style={{ maxWidth: "260px", marginTop: "0.75rem" }}>
                      <div
                        className="progress-bar-fill"
                        style={{ width: `${Math.min(100, Number(predictedScore))}%` }}
                      />
                    </div>
                  )}
                  {latestPrediction?.model_used && (
                    <p style={{ fontSize: "0.85rem", color: "var(--text-muted)", marginTop: "0.75rem" }}>
                      Model: <strong>{latestPrediction.model_used}</strong>
                      {latestPrediction.created_at && (
                        <> · Saved {new Date(latestPrediction.created_at).toLocaleString()}</>
                      )}
                    </p>
                  )}
                </div>

                <div>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem", gap: "0.75rem", flexWrap: "wrap" }}>
                    <strong>Risk Assessment</strong>
                    {riskCategory && (
                      <span className={`badge ${getRiskBadgeClass(riskCategory)}`}>{riskCategory}</span>
                    )}
                  </div>
                  {riskAssessment?.concise_explanation && (
                    <p style={{ fontSize: "0.9rem", color: "#334155", marginTop: 0 }}>
                      {riskAssessment.concise_explanation}
                    </p>
                  )}
                  {riskAssessment?.relevant_indicators?.length > 0 && (
                    <ul style={{ margin: "0 0 0.75rem 0", paddingLeft: "1.25rem", fontSize: "0.85rem", color: "#64748b" }}>
                      {riskAssessment.relevant_indicators.map((ind, i) => (
                        <li key={i}>
                          <strong>{ind.indicator} ({ind.value})</strong>: {ind.message}
                        </li>
                      ))}
                    </ul>
                  )}
                  {riskAssessment?.recommended_interventions?.length > 0 && (
                    <div style={{ background: "var(--primary-light)", padding: "0.85rem", borderRadius: "6px", fontSize: "0.85rem", color: "#312e81" }}>
                      <strong>Intervention Guidance:</strong>
                      <ul style={{ margin: "0.35rem 0 0 0", paddingLeft: "1.2rem" }}>
                        {riskAssessment.recommended_interventions.map((item, i) => (
                          <li key={i}>{item}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>

          <div className="card">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "1rem", flexWrap: "wrap", marginBottom: "1rem" }}>
              <h2 className="card-title" style={{ margin: 0 }}>Recommended Hours & Timetable</h2>
              <Link to="/planner" className="btn btn-primary btn-sm">Open Study Planner</Link>
            </div>

            {!studyPlan ? (
              <div className="empty-state-inline">
                <p style={{ color: "var(--text-muted)", marginBottom: "1rem" }}>
                  No active study plan is stored for <strong>{email}</strong>. Generate a plan so the M12
                  API can save recommended hours and a timetable for this dashboard.
                </p>
                <Link to="/planner" className="btn btn-secondary">Generate Study Plan</Link>
              </div>
            ) : (
              <>
                {(studyPlan.summary || studyPlan.notes) && (
                  <div style={{ background: "#f8fafc", border: "1px solid var(--border)", borderRadius: "8px", padding: "1rem", marginBottom: "1.25rem" }}>
                    {studyPlan.summary && (
                      <p style={{ margin: "0 0 0.5rem 0", fontSize: "0.95rem" }}>{studyPlan.summary}</p>
                    )}
                    {studyPlan.notes && (
                      <p style={{ margin: 0, fontSize: "0.85rem", color: "var(--text-muted)" }}>{studyPlan.notes}</p>
                    )}
                    <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap", marginTop: "0.75rem" }}>
                      {studyPlan.risk_category_applied && (
                        <span className={`badge ${getRiskBadgeClass(studyPlan.risk_category_applied)}`}>
                          Plan risk: {studyPlan.risk_category_applied}
                        </span>
                      )}
                      {studyPlan.plan_date && (
                        <span className="badge badge-info">Plan date: {studyPlan.plan_date}</span>
                      )}
                      {studyPlan.days_planned && (
                        <span className="badge badge-info">{studyPlan.days_planned} days planned</span>
                      )}
                    </div>
                  </div>
                )}

                {studyPlan.subject_allocations?.length > 0 && (
                  <div style={{ marginBottom: "1.5rem" }}>
                    <h3 style={{ fontSize: "1rem", marginBottom: "0.75rem" }}>Subject Hour Allocations</h3>
                    <div className="table-responsive">
                      <table className="styled-table">
                        <thead>
                          <tr>
                            <th>Subject</th>
                            <th>Difficulty</th>
                            <th>Hours</th>
                            <th>Slots</th>
                          </tr>
                        </thead>
                        <tbody>
                          {studyPlan.subject_allocations.map((row, idx) => (
                            <tr key={idx}>
                              <td>{row.subject}</td>
                              <td>{row.difficulty}</td>
                              <td>{row.allocated_study_hours}</td>
                              <td>{row.slots_count}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}

                <div style={{ display: "flex", gap: "1rem", borderBottom: "1px solid var(--border)", paddingBottom: "1rem", marginBottom: "1.5rem", flexWrap: "wrap" }}>
                  <button
                    type="button"
                    className={`btn ${scheduleTab === "daily" ? "btn-primary" : "btn-secondary"}`}
                    onClick={() => setScheduleTab("daily")}
                  >
                    Daily Timetable
                  </button>
                  <button
                    type="button"
                    className={`btn ${scheduleTab === "weekly" ? "btn-primary" : "btn-secondary"}`}
                    onClick={() => setScheduleTab("weekly")}
                  >
                    Weekly Timetable
                  </button>
                </div>

                {scheduleTab === "daily" && (
                  <div>
                    {dailySlots.length === 0 ? (
                      <p style={{ color: "var(--text-muted)" }}>No daily timetable slots were returned for this plan.</p>
                    ) : (
                      dailySlots.map((slot, idx) => (
                        <div key={slot.slot_id || idx} className="timetable-slot">
                          <div className="slot-time">
                            {slot.start_time} - {slot.end_time}
                          </div>
                          <div style={{ flex: 1, padding: "0 1.5rem" }}>
                            <div className="slot-subject">{slot.subject}</div>
                            <div className="slot-activity">{slot.recommended_focus}</div>
                          </div>
                          {slot.break_time && (
                            <div style={{ fontSize: "0.85rem", color: "var(--text-muted)", fontStyle: "italic" }}>
                              Rest: {slot.break_time}
                            </div>
                          )}
                        </div>
                      ))
                    )}
                  </div>
                )}

                {scheduleTab === "weekly" && (
                  <div>
                    {Object.keys(weeklySchedule).length === 0 ? (
                      <p style={{ color: "var(--text-muted)" }}>No weekly schedule was returned for this plan.</p>
                    ) : (
                      Object.entries(weeklySchedule).map(([dayKey, slots]) => (
                        <div key={dayKey} style={{ marginBottom: "1.75rem" }}>
                          <h3 style={{ fontSize: "1.05rem", color: "var(--primary)", borderBottom: "1px solid var(--border)", paddingBottom: "0.5rem" }}>
                            {dayKey}
                          </h3>
                          {(slots || []).map((slot, idx) => (
                            <div
                              key={slot.slot_id || idx}
                              className="timetable-slot"
                              style={{ opacity: slot.completed ? 0.65 : 1 }}
                            >
                              <div className="slot-time">
                                {slot.start_time} - {slot.end_time}
                              </div>
                              <div style={{ flex: 1, padding: "0 1.5rem" }}>
                                <div className="slot-subject">{slot.subject}</div>
                                <div className="slot-activity">{slot.recommended_focus}</div>
                              </div>
                              {slot.completed && (
                                <span className="badge badge-low">Completed</span>
                              )}
                            </div>
                          ))}
                        </div>
                      ))
                    )}
                  </div>
                )}
              </>
            )}
          </div>

          <div className="card">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "1rem", flexWrap: "wrap", marginBottom: "0.75rem" }}>
              <p style={{ margin: 0, color: "var(--text-muted)", fontSize: "0.9rem" }}>
                Upload PDF study materials, index them for RAG, and ask grounded questions with page citations.
              </p>
              <Link to="/documents" className="btn btn-secondary btn-sm">Open Materials Page</Link>
            </div>
            <PdfDocumentsPanel email={email} compact />
          </div>
        </>
      )}
    </div>
  );
}

export default Dashboard;
