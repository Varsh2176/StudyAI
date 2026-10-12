import { useState, useEffect } from "react";
import API from "../services/api";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorMessage,
  Input,
  Select,
  Skeleton,
  priorityToBadgeVariant,
  statusToBadgeVariant,
  subjectColor,
} from "../components/ui";

function StudyPlanner() {
  const [email, setEmail] = useState(() => localStorage.getItem("student_email") || "");
  const [dailyHours, setDailyHours] = useState(4.0);
  const [startTime, setStartTime] = useState("09:00");
  const [daysToPlan, setDaysToPlan] = useState(7);
  const [subjects, setSubjects] = useState([
    { name: "Machine Learning", difficulty: "High", current_score: 60, target_score: 85, exam_date: "" },
    { name: "Data Structures", difficulty: "Medium", current_score: 70, target_score: 90, exam_date: "" },
    { name: "Operating Systems", difficulty: "High", current_score: 55, target_score: 80, exam_date: "" }
  ]);

  const [loading, setLoading] = useState(false);
  const [adapting, setAdapting] = useState(false);
  const [plan, setPlan] = useState(null);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [adaptations, setAdaptations] = useState([]);
  const [activeTab, setActiveTab] = useState("daily"); // "daily" or "weekly"

  const loadSavedPlan = async (studentEmail) => {
    try {
      const res = await API.get(`/study-plan/${studentEmail}`);
      if (res.data && res.data.plan) {
        setPlan(res.data.plan);
      }
    } catch (err) {
      console.log("No saved study plan found:", err);
    }
  };

  useEffect(() => {
    if (!email) return undefined;

    let cancelled = false;
    const timer = window.setTimeout(() => {
      if (!cancelled) {
        void loadSavedPlan(email);
      }
    }, 0);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
    // Initial hydrate only — email is seeded from localStorage.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const importFromProfile = async () => {
    if (!email) return;
    try {
      const res = await API.get(`/student/${email}`);
      if (res.data && res.data.subjects) {
        const subList = Array.isArray(res.data.subjects)
          ? res.data.subjects
          : res.data.subjects.split(",").map((s) => s.trim());

        const imported = subList.filter(Boolean).map((name) => ({
          name,
          difficulty: "Medium",
          current_score: 65,
          target_score: 85,
          exam_date: ""
        }));

        if (imported.length > 0) {
          setSubjects(imported);
        }
        if (res.data.study_hours) {
          setDailyHours(Number(res.data.study_hours));
        }
      }
    } catch (err) {
      console.log("Failed to import subjects from profile:", err);
    }
  };

  const handleSubjectChange = (index, field, value) => {
    const updated = [...subjects];
    updated[index][field] = value;
    setSubjects(updated);
  };

  const addSubject = () => {
    setSubjects([
      ...subjects,
      { name: "", difficulty: "Medium", current_score: 60, target_score: 85, exam_date: "" }
    ]);
  };

  const removeSubject = (index) => {
    setSubjects(subjects.filter((_, i) => i !== index));
  };

  const handleGeneratePlan = async (e) => {
    e.preventDefault();
    setError("");
    setSuccess("");
    setAdaptations([]);
    setLoading(true);

    try {
      const validSubjects = subjects.filter((s) => s.name.trim() !== "");
      if (validSubjects.length === 0) {
        setError("Please enter at least one subject.");
        setLoading(false);
        return;
      }

      if (email) {
        localStorage.setItem("student_email", email.trim());
      }

      const res = await API.post("/study-plan/generate", {
        email: email || undefined,
        daily_study_hours: Number(dailyHours),
        preferred_start_time: startTime,
        days_to_plan: Number(daysToPlan),
        subjects: validSubjects.map((s) => ({
          ...s,
          current_score: Number(s.current_score),
          target_score: Number(s.target_score),
          exam_date: s.exam_date || null
        }))
      });

      setPlan(res.data);
      setSuccess("Study plan generated successfully.");
    } catch (err) {
      console.error(err);
      setError(err.response?.data?.detail || "Failed to generate study plan.");
    } finally {
      setLoading(false);
    }
  };

  const handleAdaptFromProgress = async () => {
    setError("");
    setSuccess("");
    setAdaptations([]);

    const trimmed = (email || "").trim();
    if (!trimmed) {
      setError("Enter your student email so adaptation can load your progress and saved plan.");
      return;
    }

    setAdapting(true);
    try {
      localStorage.setItem("student_email", trimmed);
      const res = await API.post("/performance/adapt-plan", {
        email: trimmed,
        daily_available_hours: Number(dailyHours) || undefined,
        days_to_plan: Number(daysToPlan) || undefined,
      });

      if (res.data?.adapted_plan) {
        setPlan(res.data.adapted_plan);
      }
      setAdaptations(res.data?.adaptations || []);
      if (res.data?.unchanged) {
        setSuccess(res.data.message || "Plan unchanged — no new progress to adapt.");
      } else {
        setSuccess(res.data?.message || "Plan adapted from your logged progress.");
      }
    } catch (err) {
      const status = err.response?.status;
      const detail = err.response?.data?.detail;
      if (status === 404) {
        setError(detail || "No saved plan found. Generate a plan first, then adapt.");
      } else if (status === 503) {
        setError(detail || "Database unavailable. Check /health/database.");
      } else {
        setError(detail || "Failed to adapt study plan from progress.");
      }
    } finally {
      setAdapting(false);
    }
  };

  const toggleSlotCompleted = async (dayKey, slotId) => {
    if (!plan || !email) return;

    try {
      const res = await API.put(`/study-plan/${email}/toggle-slot`, {
        day_key: dayKey,
        slot_id: slotId
      });
      if (res.data?.weekly_schedule) {
        setPlan((prev) => ({
          ...prev,
          weekly_schedule: res.data.weekly_schedule
        }));
      }
    } catch {
      // Local fallback toggle
      setPlan((prev) => {
        const copy = { ...prev };
        if (copy.weekly_schedule?.[dayKey]) {
          copy.weekly_schedule[dayKey] = copy.weekly_schedule[dayKey].map((slot) =>
            slot.slot_id === slotId ? { ...slot, completed: !slot.completed } : slot
          );
        }
        return copy;
      });
    }
  };

  const dailyHoursDisplay =
    plan?.daily_study_hours !== undefined && plan?.daily_study_hours !== null
      ? plan.daily_study_hours
      : null;
  const daysPlannedDisplay =
    plan?.days_planned !== undefined && plan?.days_planned !== null
      ? plan.days_planned
      : null;
  const totalStudyHoursDisplay =
    plan?.total_scheduled_study_hours !== undefined && plan?.total_scheduled_study_hours !== null
      ? plan.total_scheduled_study_hours
      : null;
  const subjectCountDisplay = plan?.subjects_weighted?.length ?? null;

  return (
    <div className="sw-planner page-container">
      <section className="sw-planner-intro" aria-labelledby="planner-heading">
        <h2 id="planner-heading">Personalized study planner</h2>
        <p>
          Deterministic scheduling from subject difficulty, score gaps, and exam urgency,
          with Pomodoro-style blocks (50m study / 10m break). Generate a plan or adapt from logged progress.
        </p>
      </section>

      {error ? (
        <ErrorMessage
          message={typeof error === "string" ? error : "Something went wrong."}
          onRetry={email ? () => loadSavedPlan(email) : undefined}
          retryLabel="Reload saved plan"
        />
      ) : null}

      {success ? (
        <div className="sw-planner-success" role="status">
          {success}
        </div>
      ) : null}

      {adaptations.length > 0 ? (
        <Card title="Why the plan changed" className="sw-planner-adapt-card">
          <ul className="sw-planner-adapt-list">
            {adaptations.map((note, i) => (
              <li key={i}>{note}</li>
            ))}
          </ul>
        </Card>
      ) : null}

      {plan ? (
        <div className="sw-planner-stats">
          <Card title="Daily study hours">
            {dailyHoursDisplay !== null ? (
              <div className="sw-planner-stat-value">{dailyHoursDisplay}</div>
            ) : (
              <p className="sw-planner-stat-muted">Not available</p>
            )}
          </Card>
          <Card title="Days planned">
            {daysPlannedDisplay !== null ? (
              <div className="sw-planner-stat-value">{daysPlannedDisplay}</div>
            ) : (
              <p className="sw-planner-stat-muted">Not available</p>
            )}
          </Card>
          <Card title="Scheduled study">
            {totalStudyHoursDisplay !== null ? (
              <div className="sw-planner-stat-value">
                {totalStudyHoursDisplay}
                <span className="sw-planner-stat-muted"> hrs</span>
              </div>
            ) : (
              <p className="sw-planner-stat-muted">Not available</p>
            )}
          </Card>
          <Card title="Subjects weighted">
            {subjectCountDisplay !== null ? (
              <div className="sw-planner-stat-value">{subjectCountDisplay}</div>
            ) : (
              <p className="sw-planner-stat-muted">Not available</p>
            )}
          </Card>
        </div>
      ) : null}

      <Card
        title="Plan parameters & subjects"
        action={
          <div className="sw-planner-actions">
            {email ? (
              <Button type="button" variant="secondary" size="sm" onClick={importFromProfile}>
                Import from profile
              </Button>
            ) : null}
            <Button
              type="button"
              variant="primary"
              size="sm"
              loading={adapting}
              disabled={adapting || loading}
              onClick={handleAdaptFromProgress}
            >
              {adapting ? "Adapting..." : "Adapt from progress"}
            </Button>
          </div>
        }
      >
        <form onSubmit={handleGeneratePlan}>
          <Input
            id="planner-email"
            label="Student email (required to save / adapt)"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@college.edu"
          />

          <div className="sw-planner-form-grid">
            <Input
              label="Daily study availability (hours)"
              type="number"
              min="1"
              max="10"
              step="0.5"
              value={dailyHours}
              onChange={(e) => setDailyHours(e.target.value)}
              hint="Capped at 10 hrs to protect against cognitive fatigue"
              required
            />
            <Input
              label="Preferred study start time"
              type="time"
              value={startTime}
              onChange={(e) => setStartTime(e.target.value)}
              required
            />
            <Select
              label="Days to plan ahead"
              value={daysToPlan}
              onChange={(e) => setDaysToPlan(Number(e.target.value))}
            >
              <option value={3}>3 Days</option>
              <option value={7}>7 Days (1 Week)</option>
              <option value={14}>14 Days (2 Weeks)</option>
            </Select>
          </div>

          <h3 className="sw-planner-subjects-title">Subjects to balance</h3>

          <div className="sw-planner-table-wrap">
            <table className="sw-planner-table">
              <thead>
                <tr>
                  <th>Subject</th>
                  <th>Difficulty</th>
                  <th>Current %</th>
                  <th>Target %</th>
                  <th>Exam date</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {subjects.map((subj, idx) => (
                  <tr key={idx}>
                    <td>
                      <input
                        type="text"
                        placeholder="Subject name"
                        value={subj.name}
                        onChange={(e) => handleSubjectChange(idx, "name", e.target.value)}
                        required
                        aria-label={`Subject name ${idx + 1}`}
                      />
                    </td>
                    <td>
                      <select
                        value={subj.difficulty}
                        onChange={(e) => handleSubjectChange(idx, "difficulty", e.target.value)}
                        aria-label={`Difficulty ${idx + 1}`}
                      >
                        <option value="Low">Low</option>
                        <option value="Medium">Medium</option>
                        <option value="High">High</option>
                      </select>
                    </td>
                    <td>
                      <input
                        type="number"
                        min="0"
                        max="100"
                        value={subj.current_score}
                        onChange={(e) => handleSubjectChange(idx, "current_score", e.target.value)}
                        aria-label={`Current score ${idx + 1}`}
                      />
                    </td>
                    <td>
                      <input
                        type="number"
                        min="0"
                        max="100"
                        value={subj.target_score}
                        onChange={(e) => handleSubjectChange(idx, "target_score", e.target.value)}
                        aria-label={`Target score ${idx + 1}`}
                      />
                    </td>
                    <td>
                      <input
                        type="date"
                        value={subj.exam_date}
                        onChange={(e) => handleSubjectChange(idx, "exam_date", e.target.value)}
                        aria-label={`Exam date ${idx + 1}`}
                      />
                    </td>
                    <td>
                      {subjects.length > 1 ? (
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          onClick={() => removeSubject(idx)}
                          aria-label={`Remove subject ${idx + 1}`}
                        >
                          Remove
                        </Button>
                      ) : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="sw-planner-form-footer">
            <Button type="button" variant="secondary" onClick={addSubject}>
              + Add subject
            </Button>
            <Button type="submit" variant="primary" loading={loading} disabled={loading}>
              {loading ? "Generating schedule..." : "Generate study plan"}
            </Button>
          </div>
        </form>
      </Card>

      {loading && !plan ? (
        <div aria-busy="true" aria-label="Generating plan">
          <Skeleton variant="card" />
          <Skeleton variant="block" />
        </div>
      ) : null}

      {!loading && !plan ? (
        <EmptyState
          title="No study plan yet"
          description="Configure subjects above and generate a deterministic timetable, or adapt from progress if you already have a saved plan."
        />
      ) : null}

      {plan ? (
        <div>
          <Card title="Subject priority weightings">
            {!plan.subjects_weighted?.length ? (
              <p className="sw-planner-stat-muted">No subject weightings returned for this plan.</p>
            ) : (
              <div className="sw-planner-weight-grid">
                {plan.subjects_weighted.map((sw, idx) => {
                  const colors = subjectColor(sw.name || `subject-${idx}`);
                  const gap =
                    sw.target_score !== undefined && sw.current_score !== undefined
                      ? Number(sw.target_score) - Number(sw.current_score)
                      : null;
                  const share =
                    sw.allocated_ratio !== undefined && sw.allocated_ratio !== null
                      ? Math.round(Number(sw.allocated_ratio) * 100)
                      : null;
                  return (
                    <div key={idx} className="sw-planner-weight-card">
                      <div className="sw-planner-weight-head">
                        <strong style={{ color: colors.solid }}>{sw.name}</strong>
                        {share !== null && !Number.isNaN(share) ? (
                          <Badge variant="info">{share}% time share</Badge>
                        ) : null}
                      </div>
                      <div className="sw-planner-stat-muted">
                        Difficulty: <strong>{sw.difficulty}</strong>
                        {gap !== null && !Number.isNaN(gap) ? (
                          <> · Score gap: <strong>{gap} pts</strong></>
                        ) : null}
                        {sw.priority_level ? (
                          <>
                            {" · "}
                            <Badge variant={priorityToBadgeVariant(sw.priority_level)}>
                              {sw.priority_level}
                            </Badge>
                          </>
                        ) : null}
                        {sw.days_left !== null && sw.days_left !== undefined ? (
                          <div>
                            Exam in:{" "}
                            <strong
                              style={{
                                color:
                                  Number(sw.days_left) <= 7
                                    ? "var(--sw-danger)"
                                    : "var(--sw-text)",
                              }}
                            >
                              {sw.days_left} days
                            </strong>
                          </div>
                        ) : null}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </Card>

          <Card title="Timetable">
            <div className="sw-planner-tabs">
              <Button
                type="button"
                variant={activeTab === "daily" ? "primary" : "secondary"}
                size="sm"
                onClick={() => setActiveTab("daily")}
              >
                Daily timetable
              </Button>
              <Button
                type="button"
                variant={activeTab === "weekly" ? "primary" : "secondary"}
                size="sm"
                onClick={() => setActiveTab("weekly")}
              >
                Weekly timetable
                {daysPlannedDisplay !== null ? ` (${daysPlannedDisplay} days)` : ""}
              </Button>
            </div>

            {activeTab === "daily" && (
              <div>
                <h3 className="sw-planner-subjects-title">
                  Scheduled slots
                  {dailyHoursDisplay !== null ? ` (${dailyHoursDisplay} hours)` : ""}
                </h3>
                {!plan.daily_schedule?.length ? (
                  <EmptyState
                    title="No daily slots"
                    description="This plan did not return a daily_schedule."
                  />
                ) : (
                  plan.daily_schedule.map((slot, idx) => {
                    const colors = subjectColor(slot.subject || "session");
                    return (
                      <div key={slot.slot_id || idx} className="sw-planner-slot">
                        <div
                          className="sw-planner-slot-accent"
                          style={{ background: colors.solid }}
                          aria-hidden="true"
                        />
                        <div className="sw-planner-slot-time">
                          {slot.start_time} – {slot.end_time}
                        </div>
                        <div className="sw-planner-slot-body">
                          <div className="sw-planner-slot-subject" style={{ color: colors.solid }}>
                            {slot.subject}
                          </div>
                          <div className="sw-planner-slot-focus">{slot.recommended_focus}</div>
                        </div>
                        {slot.break_time ? (
                          <span className="sw-planner-stat-muted">Rest: {slot.break_time}</span>
                        ) : null}
                        <Badge variant={statusToBadgeVariant("planned")}>planned</Badge>
                      </div>
                    );
                  })
                )}
              </div>
            )}

            {activeTab === "weekly" && (
              <div>
                {!plan.weekly_schedule || Object.keys(plan.weekly_schedule).length === 0 ? (
                  <EmptyState
                    title="No weekly schedule"
                    description="This plan did not return a weekly_schedule."
                  />
                ) : (
                  Object.entries(plan.weekly_schedule).map(([dayKey, slots]) => (
                    <div key={dayKey} className="sw-planner-day">
                      <h3>{dayKey}</h3>
                      {(slots || []).map((slot, idx) => {
                        const colors = subjectColor(slot.subject || "session");
                        const statusLabel = slot.completed ? "completed" : "planned";
                        return (
                          <div
                            key={slot.slot_id || idx}
                            className={`sw-planner-slot${slot.completed ? " sw-planner-slot--done" : ""}`}
                          >
                            <div
                              className="sw-planner-slot-accent"
                              style={{ background: colors.solid }}
                              aria-hidden="true"
                            />
                            <div className="sw-planner-check">
                              <input
                                type="checkbox"
                                checked={!!slot.completed}
                                onChange={() => toggleSlotCompleted(dayKey, slot.slot_id)}
                                aria-label={`Mark ${slot.subject || "session"} on ${dayKey} complete`}
                              />
                              <div className="sw-planner-slot-time">
                                {slot.start_time} – {slot.end_time}
                              </div>
                            </div>
                            <div className="sw-planner-slot-body">
                              <div className="sw-planner-slot-subject" style={{ color: colors.solid }}>
                                {slot.subject}
                              </div>
                              <div className="sw-planner-slot-focus">{slot.recommended_focus}</div>
                            </div>
                            {slot.break_time ? (
                              <span className="sw-planner-stat-muted">{slot.break_time}</span>
                            ) : null}
                            <Badge variant={statusToBadgeVariant(statusLabel)}>{statusLabel}</Badge>
                          </div>
                        );
                      })}
                    </div>
                  ))
                )}
              </div>
            )}
          </Card>
        </div>
      ) : null}
    </div>
  );
}

export default StudyPlanner;
