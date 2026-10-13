import { useState, useEffect, useCallback } from "react";
import { Link } from "react-router-dom";
import API from "../services/api";
import PdfDocumentsPanel from "../components/PdfDocumentsPanel";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorMessage,
  Input,
  ProgressBar,
  Skeleton,
  riskToBadgeVariant,
  statusToBadgeVariant,
  subjectColor,
  IconPredict,
  IconPlanner,
  IconTutor,
  IconDocuments,
  IconProgress,
  IconProfile,
} from "../components/ui";

function parseTimeToMinutes(value) {
  if (!value || typeof value !== "string") return null;
  const match = value.trim().match(/^(\d{1,2}):(\d{2})$/);
  if (!match) return null;
  const hours = Number(match[1]);
  const mins = Number(match[2]);
  if (Number.isNaN(hours) || Number.isNaN(mins)) return null;
  return hours * 60 + mins;
}

function slotDurationLabel(slot) {
  const start = parseTimeToMinutes(slot?.start_time);
  const end = parseTimeToMinutes(slot?.end_time);
  if (start === null || end === null || end <= start) return null;
  const mins = end - start;
  if (mins < 60) return `${mins} min`;
  const h = Math.floor(mins / 60);
  const m = mins % 60;
  return m ? `${h}h ${m}m` : `${h}h`;
}

function formatNumber(value) {
  if (value === null || value === undefined) return null;
  const n = Number(value);
  if (Number.isNaN(n)) return null;
  return n;
}

function Dashboard() {
  const [emailInput, setEmailInput] = useState(
    () => localStorage.getItem("student_email") || ""
  );
  const [email, setEmail] = useState(
    () => localStorage.getItem("student_email") || ""
  );
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
    window.dispatchEvent(new Event("studyai-identity-changed"));

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

  const scoreNum = formatNumber(predictedScore);
  const dailyHoursNum = formatNumber(recommendedDailyHours);
  const weeklyHoursNum = formatNumber(recommendedWeeklyHours);
  const availabilityNum = formatNumber(
    profile?.study_hours ?? studyPlan?.daily_available_hours
  );

  // Today's progress from plan slots that expose `completed` (weekly), else daily list length only for empty check
  const weeklyFlat = Object.values(weeklySchedule).flatMap((slots) => slots || []);
  const slotsWithCompletion = weeklyFlat.filter((s) => typeof s?.completed === "boolean");
  const completedCount = slotsWithCompletion.filter((s) => s.completed).length;
  const todayProgressAvailable = slotsWithCompletion.length > 0;
  const todayProgressPercent = todayProgressAvailable
    ? Math.round((completedCount / slotsWithCompletion.length) * 100)
    : null;

  const allocations = studyPlan?.subject_allocations || [];
  const maxAllocHours = allocations.reduce((max, row) => {
    const h = formatNumber(row?.allocated_study_hours);
    return h !== null && h > max ? h : max;
  }, 0);

  const welcomeLine = profile?.course
    ? `${profile.course}${profile.branch ? ` · ${profile.branch}` : ""}${
        profile.year != null && profile.year !== "" ? ` · Year ${profile.year}` : ""
      }`
    : email
      ? `Showing saved data for ${email}`
      : "Load the student email you used at registration to see live academic data.";

  const welcomeTitle = profile?.course
    ? "Welcome back"
    : email
      ? "Student overview"
      : "Your study dashboard";

  return (
    <div className="sw-dash page-container">
      <section className="sw-dash-welcome" aria-labelledby="dash-welcome-heading">
        <p className="sw-dash-welcome-eyebrow">StudyWise AI</p>
        <h2 id="dash-welcome-heading">{welcomeTitle}</h2>
        <p>{welcomeLine}</p>
        {email || profile ? (
          <div className="sw-dash-welcome-meta">
            {email ? <Badge variant="primary">{email}</Badge> : null}
            {riskCategory ? (
              <Badge variant={riskToBadgeVariant(riskCategory)}>{riskCategory}</Badge>
            ) : null}
            {studyPlan?.plan_date ? (
              <Badge variant="info">Plan: {studyPlan.plan_date}</Badge>
            ) : null}
          </div>
        ) : null}
      </section>

      <Card title="Load student data" className="sw-dash-load-card">
        <form className="sw-dash-email-form" onSubmit={handleLoadSubmit}>
          <Input
            id="dashboard-email"
            label="Student Email"
            type="email"
            placeholder="student@example.edu"
            value={emailInput}
            onChange={(e) => setEmailInput(e.target.value)}
            required
            hint="Uses the same local identity key as the rest of the app."
          />
          <div className="sw-dash-email-actions">
            <Button type="submit" variant="primary" loading={loading} disabled={loading}>
              {loading ? "Loading..." : "Load Dashboard"}
            </Button>
            <Button
              type="button"
              variant="secondary"
              onClick={() => loadDashboard(email || emailInput)}
              disabled={loading || !(email || emailInput)}
            >
              Retry
            </Button>
          </div>
        </form>
      </Card>

      {error ? (
        <ErrorMessage
          message={error}
          onRetry={() => loadDashboard(email || emailInput)}
          retryLabel="Retry"
        />
      ) : null}

      {loading ? (
        <div aria-busy="true" aria-label="Loading dashboard">
          <div className="sw-dash-skeleton-grid">
            <Skeleton variant="card" />
            <Skeleton variant="card" />
            <Skeleton variant="card" />
            <Skeleton variant="card" />
          </div>
          <Skeleton variant="card" />
          <Skeleton variant="block" />
        </div>
      ) : null}

      {!loading && !email && !error ? (
        <EmptyState
          title="No student selected"
          description="Register or enter the email you used for your student profile to view real dashboard data."
          action={
            <Link to="/" className="sw-btn sw-btn--primary sw-btn--md sw-dash-action-link">
              Go to Registration
            </Link>
          }
        />
      ) : null}

      {!loading && email ? (
        <>
          {loadNotes.length > 0 ? (
            <div className="sw-dash-notes" role="status">
              <ul>
                {loadNotes.map((note, idx) => (
                  <li key={idx}>{note}</li>
                ))}
              </ul>
            </div>
          ) : null}

          <section className="sw-dash-section" aria-labelledby="dash-overview-heading">
            <h3 id="dash-overview-heading" className="sw-dash-section-heading">
              Study overview
            </h3>
            <div className="sw-dash-stats">
              <Card title="Predicted exam score" className="sw-dash-stat-card">
                {scoreNum !== null ? (
                  <div className="sw-dash-stat-value">
                    {scoreNum}
                    <span className="sw-dash-stat-muted"> / 100</span>
                  </div>
                ) : (
                  <p className="sw-dash-stat-na">Not available yet</p>
                )}
                {scoreNum === null ? (
                  <Link to="/predict" className="sw-btn sw-btn--secondary sw-btn--sm sw-dash-action-link">
                    Predict Score
                  </Link>
                ) : null}
              </Card>

              <Card title="Academic risk" className="sw-dash-stat-card">
                {riskCategory ? (
                  <div className="sw-dash-stat-value">
                    <Badge variant={riskToBadgeVariant(riskCategory)}>{riskCategory}</Badge>
                  </div>
                ) : (
                  <p className="sw-dash-stat-na">Not available yet</p>
                )}
                {!riskCategory ? (
                  <Link to="/predict" className="sw-btn sw-btn--secondary sw-btn--sm sw-dash-action-link">
                    Assess Risk
                  </Link>
                ) : null}
              </Card>

              <Card title="Recommended study hours" className="sw-dash-stat-card">
                {dailyHoursNum !== null ? (
                  <>
                    <div className="sw-dash-stat-value">
                      {dailyHoursNum}
                      <span className="sw-dash-stat-muted"> hrs/day</span>
                    </div>
                    {weeklyHoursNum !== null ? (
                      <div className="sw-dash-stat-muted">{weeklyHoursNum} hrs/week</div>
                    ) : null}
                  </>
                ) : (
                  <p className="sw-dash-stat-na">Not available yet</p>
                )}
                {dailyHoursNum === null ? (
                  <Link to="/planner" className="sw-btn sw-btn--secondary sw-btn--sm sw-dash-action-link">
                    Generate Plan
                  </Link>
                ) : null}
              </Card>

              <Card title="Daily availability" className="sw-dash-stat-card">
                {availabilityNum !== null ? (
                  <div className="sw-dash-stat-value">
                    {availabilityNum}
                    <span className="sw-dash-stat-muted"> hrs/day</span>
                  </div>
                ) : (
                  <p className="sw-dash-stat-na">Not available yet</p>
                )}
              </Card>
            </div>
          </section>

          <Card title="Study progress" className="sw-dash-section">
            {todayProgressAvailable && todayProgressPercent !== null ? (
              <ProgressBar
                value={todayProgressPercent}
                label={`${completedCount} of ${slotsWithCompletion.length} planned sessions marked complete`}
                color={todayProgressPercent >= 70 ? "success" : todayProgressPercent >= 40 ? "warning" : "primary"}
              />
            ) : (
              <EmptyState
                title="Progress not available yet"
                description={
                  studyPlan
                    ? "Completion status appears after sessions in your saved weekly timetable are marked complete in the Study Planner."
                    : "Generate a study plan to track planned versus completed sessions."
                }
                action={
                  <Link to="/planner" className="sw-btn sw-btn--secondary sw-btn--sm sw-dash-action-link">
                    Open Study Planner
                  </Link>
                }
              />
            )}
          </Card>

          <section className="sw-dash-section" aria-labelledby="dash-quick-heading">
            <h3 id="dash-quick-heading" className="sw-dash-section-heading">
              Quick access
            </h3>
            <nav className="sw-dash-actions" aria-label="Dashboard quick actions">
              <Link to="/predict" className="sw-dash-action-tile">
                <span className="sw-dash-action-tile-icon">
                  <IconPredict size={18} />
                </span>
                <span className="sw-dash-action-tile-label">Predict Score</span>
              </Link>
              <Link to="/planner" className="sw-dash-action-tile">
                <span className="sw-dash-action-tile-icon">
                  <IconPlanner size={18} />
                </span>
                <span className="sw-dash-action-tile-label">Study Planner</span>
              </Link>
              <Link to="/tutor" className="sw-dash-action-tile">
                <span className="sw-dash-action-tile-icon">
                  <IconTutor size={18} />
                </span>
                <span className="sw-dash-action-tile-label">AI Tutor</span>
              </Link>
              <Link to="/documents" className="sw-dash-action-tile">
                <span className="sw-dash-action-tile-icon">
                  <IconDocuments size={18} />
                </span>
                <span className="sw-dash-action-tile-label">Documents</span>
              </Link>
              <Link to="/progress" className="sw-dash-action-tile">
                <span className="sw-dash-action-tile-icon">
                  <IconProgress size={18} />
                </span>
                <span className="sw-dash-action-tile-label">Progress</span>
              </Link>
              <Link to="/profile" className="sw-dash-action-tile">
                <span className="sw-dash-action-tile-icon">
                  <IconProfile size={18} />
                </span>
                <span className="sw-dash-action-tile-label">Profile</span>
              </Link>
            </nav>
          </section>

          <Card
            title="Student profile"
            action={
              <Link to="/profile" className="sw-btn sw-btn--secondary sw-btn--sm sw-dash-action-link">
                {profile ? "Edit Profile" : "Create Profile"}
              </Link>
            }
          >
            {!profile ? (
              <EmptyState
                title="No profile data"
                description={`No profile data returned for ${email}. Save a profile to populate this section.`}
              />
            ) : (
              <div className="sw-dash-profile-grid">
                <div><span className="detail-label">Email</span><span>{profile.email}</span></div>
                <div><span className="detail-label">Course</span><span>{profile.course}</span></div>
                <div><span className="detail-label">Branch</span><span>{profile.branch}</span></div>
                <div><span className="detail-label">Year</span><span>{profile.year}</span></div>
                <div><span className="detail-label">Age</span><span>{profile.age}</span></div>
                <div><span className="detail-label">Attendance</span><span>{profile.attendance}%</span></div>
                <div><span className="detail-label">Previous CGPA</span><span>{profile.previous_cgpa}</span></div>
                <div><span className="detail-label">Study Hours</span><span>{profile.study_hours} hrs/day</span></div>
                <div className="sw-dash-subjects">
                  <span className="detail-label">Subjects</span>
                  <div className="sw-dash-chip-row">
                    {subjects.length > 0 ? (
                      subjects.map((subject) => {
                        const colors = subjectColor(subject);
                        return (
                          <Badge
                            key={subject}
                            variant="primary"
                            style={{ background: colors.soft, color: colors.solid }}
                          >
                            {subject}
                          </Badge>
                        );
                      })
                    ) : (
                      <span className="sw-dash-stat-muted">None listed</span>
                    )}
                  </div>
                </div>
              </div>
            )}
          </Card>

          <Card
            title="Prediction & risk details"
            action={
              <Link to="/predict" className="sw-btn sw-btn--secondary sw-btn--sm sw-dash-action-link">
                Open Predictor
              </Link>
            }
          >
            {!latestPrediction && !riskAssessment ? (
              <EmptyState
                title="No prediction yet"
                description="Prediction history is empty for this student. After you run a prediction with your email, the latest score and risk assessment appear here."
                action={
                  <Link to="/predict" className="sw-btn sw-btn--primary sw-btn--sm sw-dash-action-link">
                    Run prediction
                  </Link>
                }
              />
            ) : (
              <div className="sw-dash-split">
                <div>
                  <div className="sw-dash-section-label">Latest predicted score</div>
                  <div className="sw-dash-score-big">
                    {scoreNum !== null ? scoreNum : "—"}
                    {scoreNum !== null ? (
                      <span className="sw-dash-stat-muted"> / 100</span>
                    ) : null}
                  </div>
                  {scoreNum !== null ? (
                    <ProgressBar
                      value={Math.min(100, scoreNum)}
                      label="Predicted score out of 100"
                      color="primary"
                    />
                  ) : null}
                  {latestPrediction?.model_used ? (
                    <p className="sw-dash-stat-muted sw-dash-model-meta">
                      Model: <strong>{latestPrediction.model_used}</strong>
                      {latestPrediction.created_at ? (
                        <> · Saved {new Date(latestPrediction.created_at).toLocaleString()}</>
                      ) : null}
                    </p>
                  ) : null}
                </div>

                <div>
                  <div className="sw-dash-risk-header">
                    <strong>Risk assessment</strong>
                    {riskCategory ? (
                      <Badge variant={riskToBadgeVariant(riskCategory)}>{riskCategory}</Badge>
                    ) : null}
                  </div>
                  {riskAssessment?.concise_explanation ? (
                    <p className="sw-dash-risk-copy">
                      {riskAssessment.concise_explanation}
                    </p>
                  ) : null}
                  {riskAssessment?.relevant_indicators?.length > 0 ? (
                    <ul className="sw-dash-risk-list">
                      {riskAssessment.relevant_indicators.map((ind, i) => (
                        <li key={i}>
                          <strong>{ind.indicator} ({ind.value})</strong>: {ind.message}
                        </li>
                      ))}
                    </ul>
                  ) : null}
                  {riskAssessment?.recommended_interventions?.length > 0 ? (
                    <div className="sw-dash-risk-box">
                      <strong>Intervention guidance</strong>
                      <ul>
                        {riskAssessment.recommended_interventions.map((item, i) => (
                          <li key={i}>{item}</li>
                        ))}
                      </ul>
                    </div>
                  ) : null}
                </div>
              </div>
            )}
          </Card>

          <Card title="Subject-wise plan allocation">
            {allocations.length === 0 ? (
              <EmptyState
                title="No subject allocations"
                description="Subject hour allocations appear after a study plan is generated and saved."
                action={
                  <Link to="/planner" className="sw-btn sw-btn--secondary sw-btn--sm sw-dash-action-link">
                    Generate Study Plan
                  </Link>
                }
              />
            ) : (
              <div
                className="sw-dash-alloc-list"
                role="img"
                aria-label="Subject study hour allocations from the saved plan"
              >
                {allocations.map((row, idx) => {
                  const hours = formatNumber(row.allocated_study_hours);
                  const colors = subjectColor(row.subject || `subject-${idx}`);
                  const widthPct =
                    hours !== null && maxAllocHours > 0
                      ? Math.round((hours / maxAllocHours) * 100)
                      : 0;
                  return (
                    <div key={idx} className="sw-dash-alloc-row">
                      <div className="sw-dash-alloc-meta">
                        <span>
                          <strong style={{ color: colors.solid }}>{row.subject}</strong>
                          {row.difficulty ? (
                            <span className="sw-dash-stat-muted"> · {row.difficulty}</span>
                          ) : null}
                        </span>
                        <span className="sw-dash-stat-muted">
                          {hours !== null ? `${hours} hrs` : "Not available"}
                          {row.slots_count != null ? ` · ${row.slots_count} slots` : ""}
                        </span>
                      </div>
                      <div
                        className="sw-dash-alloc-bar"
                        aria-hidden="true"
                      >
                        <div
                          className="sw-dash-alloc-fill"
                          style={{
                            width: `${widthPct}%`,
                            backgroundColor: colors.solid,
                          }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </Card>

          <Card
            title="Upcoming study sessions"
            action={
              <Link to="/planner" className="sw-btn sw-btn--primary sw-btn--sm sw-dash-action-link">
                Open Study Planner
              </Link>
            }
          >
            {!studyPlan ? (
              <EmptyState
                title="No active study plan"
                description={`No active study plan is stored for ${email}. Generate a plan so the API can save recommended hours and a timetable.`}
                action={
                  <Link to="/planner" className="sw-btn sw-btn--secondary sw-btn--sm sw-dash-action-link">
                    Generate Study Plan
                  </Link>
                }
              />
            ) : (
              <>
                {(studyPlan.summary || studyPlan.notes) && (
                  <div className="sw-dash-plan-meta">
                    {studyPlan.summary ? (
                      <p className="sw-dash-plan-summary">{studyPlan.summary}</p>
                    ) : null}
                    {studyPlan.notes ? (
                      <p className="sw-dash-stat-muted sw-dash-plan-notes">{studyPlan.notes}</p>
                    ) : null}
                    <div className="sw-dash-chip-row sw-dash-plan-chips">
                      {studyPlan.risk_category_applied ? (
                        <Badge variant={riskToBadgeVariant(studyPlan.risk_category_applied)}>
                          Plan risk: {studyPlan.risk_category_applied}
                        </Badge>
                      ) : null}
                      {studyPlan.plan_date ? (
                        <Badge variant="info">Plan date: {studyPlan.plan_date}</Badge>
                      ) : null}
                      {studyPlan.days_planned ? (
                        <Badge variant="info">{studyPlan.days_planned} days planned</Badge>
                      ) : null}
                    </div>
                  </div>
                )}

                <div className="sw-dash-tabs">
                  <Button
                    type="button"
                    variant={scheduleTab === "daily" ? "primary" : "secondary"}
                    size="sm"
                    onClick={() => setScheduleTab("daily")}
                  >
                    Daily Timetable
                  </Button>
                  <Button
                    type="button"
                    variant={scheduleTab === "weekly" ? "primary" : "secondary"}
                    size="sm"
                    onClick={() => setScheduleTab("weekly")}
                  >
                    Weekly Timetable
                  </Button>
                </div>

                {scheduleTab === "daily" && (
                  <div>
                    {dailySlots.length === 0 ? (
                      <p className="sw-dash-stat-na">No daily timetable slots were returned for this plan.</p>
                    ) : (
                      dailySlots.map((slot, idx) => {
                        const colors = subjectColor(slot.subject || "session");
                        const duration = slotDurationLabel(slot);
                        const statusLabel =
                          typeof slot.completed === "boolean"
                            ? slot.completed
                              ? "completed"
                              : "planned"
                            : "planned";
                        return (
                          <div key={slot.slot_id || idx} className="sw-dash-session">
                            <div
                              className="sw-dash-session-accent"
                              style={{ background: colors.solid }}
                              aria-hidden="true"
                            />
                            <div className="sw-dash-session-time">
                              {slot.start_time} – {slot.end_time}
                            </div>
                            <div className="sw-dash-session-body">
                              <div className="sw-dash-session-subject" style={{ color: colors.solid }}>
                                {slot.subject}
                              </div>
                              <div className="sw-dash-session-focus">{slot.recommended_focus}</div>
                              {duration ? (
                                <div className="sw-dash-stat-muted">Planned: {duration}</div>
                              ) : null}
                              {slot.break_time ? (
                                <div className="sw-dash-stat-muted">Rest: {slot.break_time}</div>
                              ) : null}
                            </div>
                            <Badge variant={statusToBadgeVariant(statusLabel)}>{statusLabel}</Badge>
                          </div>
                        );
                      })
                    )}
                  </div>
                )}

                {scheduleTab === "weekly" && (
                  <div>
                    {Object.keys(weeklySchedule).length === 0 ? (
                      <p className="sw-dash-stat-na">No weekly schedule was returned for this plan.</p>
                    ) : (
                      Object.entries(weeklySchedule).map(([dayKey, slots]) => (
                        <div key={dayKey} className="sw-dash-week-day">
                          <h3>{dayKey}</h3>
                          {(slots || []).map((slot, idx) => {
                            const colors = subjectColor(slot.subject || "session");
                            const duration = slotDurationLabel(slot);
                            const statusLabel = slot.completed ? "completed" : "planned";
                            return (
                              <div
                                key={slot.slot_id || idx}
                                className={`sw-dash-session${slot.completed ? " sw-dash-session--done" : ""}`}
                              >
                                <div
                                  className="sw-dash-session-accent"
                                  style={{ background: colors.solid }}
                                  aria-hidden="true"
                                />
                                <div className="sw-dash-session-time">
                                  {slot.start_time} – {slot.end_time}
                                </div>
                                <div className="sw-dash-session-body">
                                  <div className="sw-dash-session-subject" style={{ color: colors.solid }}>
                                    {slot.subject}
                                  </div>
                                  <div className="sw-dash-session-focus">{slot.recommended_focus}</div>
                                  {duration ? (
                                    <div className="sw-dash-stat-muted">Planned: {duration}</div>
                                  ) : null}
                                </div>
                                <Badge variant={statusToBadgeVariant(statusLabel)}>{statusLabel}</Badge>
                              </div>
                            );
                          })}
                        </div>
                      ))
                    )}
                  </div>
                )}
              </>
            )}
          </Card>

          <Card title="Study materials">
            <div className="sw-dash-materials-intro">
              <p>
                Upload PDF study materials, index them for RAG, and ask grounded questions with page citations.
              </p>
              <Link to="/documents" className="sw-btn sw-btn--secondary sw-btn--sm sw-dash-action-link">
                Open Materials Page
              </Link>
            </div>
            <PdfDocumentsPanel email={email} compact />
          </Card>
        </>
      ) : null}
    </div>
  );
}

export default Dashboard;
