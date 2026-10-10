import { useState, useEffect } from "react";
import API from "../services/api";

function StudyPlanner() {
  const [email, setEmail] = useState("");
  const [dailyHours, setDailyHours] = useState(4.0);
  const [startTime, setStartTime] = useState("09:00");
  const [daysToPlan, setDaysToPlan] = useState(7);
  const [subjects, setSubjects] = useState([
    { name: "Machine Learning", difficulty: "High", current_score: 60, target_score: 85, exam_date: "" },
    { name: "Data Structures", difficulty: "Medium", current_score: 70, target_score: 90, exam_date: "" },
    { name: "Operating Systems", difficulty: "High", current_score: 55, target_score: 80, exam_date: "" }
  ]);

  const [loading, setLoading] = useState(false);
  const [plan, setPlan] = useState(null);
  const [error, setError] = useState("");
  const [activeTab, setActiveTab] = useState("daily"); // "daily" or "weekly"

  useEffect(() => {
    const savedEmail = localStorage.getItem("student_email");
    if (savedEmail) {
      setEmail(savedEmail);
      loadSavedPlan(savedEmail);
    }
  }, []);

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
    setLoading(true);

    try {
      const validSubjects = subjects.filter((s) => s.name.trim() !== "");
      if (validSubjects.length === 0) {
        setError("Please enter at least one subject.");
        setLoading(false);
        return;
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
    } catch (err) {
      console.error(err);
      setError(err.response?.data?.detail || "Failed to generate study plan.");
    } finally {
      setLoading(false);
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
    } catch (err) {
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

  return (
    <div className="page-container">
      <div className="page-header">
        <h1>Personalized Study Planner</h1>
        <p>
          Deterministic scheduling engine calculating urgency, score gaps, and difficulty weights
          with Pomodoro interval blocks (50m study / 10m break).
        </p>
      </div>

      {error && <div className="alert alert-danger">{error}</div>}

      <div className="card">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.25rem" }}>
          <h2 className="card-title" style={{ margin: 0 }}>Plan Parameters & Subjects</h2>
          {email && (
            <button type="button" className="btn btn-secondary btn-sm" onClick={importFromProfile}>
              Import Subjects from Profile
            </button>
          )}
        </div>

        <form onSubmit={handleGeneratePlan}>
          <div className="form-grid" style={{ marginBottom: "1.5rem" }}>
            <div className="form-group">
              <label>Daily Study Availability (Hours)</label>
              <input
                type="number"
                min="1"
                max="10"
                step="0.5"
                value={dailyHours}
                onChange={(e) => setDailyHours(e.target.value)}
                required
              />
              <span className="form-help">Capped at 10 hrs to protect against cognitive fatigue</span>
            </div>

            <div className="form-group">
              <label>Preferred Study Start Time</label>
              <input
                type="time"
                value={startTime}
                onChange={(e) => setStartTime(e.target.value)}
                required
              />
            </div>

            <div className="form-group">
              <label>Days to Plan Ahead</label>
              <select value={daysToPlan} onChange={(e) => setDaysToPlan(Number(e.target.value))}>
                <option value={3}>3 Days</option>
                <option value={7}>7 Days (1 Week)</option>
                <option value={14}>14 Days (2 Weeks)</option>
              </select>
            </div>
          </div>

          <h3 style={{ fontSize: "1rem", color: "#334155", marginBottom: "0.75rem" }}>Subjects to Balance</h3>

          <div className="table-responsive" style={{ marginBottom: "1rem" }}>
            <table className="styled-table">
              <thead>
                <tr>
                  <th>Subject Name</th>
                  <th>Difficulty</th>
                  <th>Current Marks (%)</th>
                  <th>Target Marks (%)</th>
                  <th>Exam Date (Optional)</th>
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
                        style={{ width: "100%", padding: "0.4rem" }}
                      />
                    </td>
                    <td>
                      <select
                        value={subj.difficulty}
                        onChange={(e) => handleSubjectChange(idx, "difficulty", e.target.value)}
                        style={{ padding: "0.4rem" }}
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
                        style={{ width: "80px", padding: "0.4rem" }}
                      />
                    </td>
                    <td>
                      <input
                        type="number"
                        min="0"
                        max="100"
                        value={subj.target_score}
                        onChange={(e) => handleSubjectChange(idx, "target_score", e.target.value)}
                        style={{ width: "80px", padding: "0.4rem" }}
                      />
                    </td>
                    <td>
                      <input
                        type="date"
                        value={subj.exam_date}
                        onChange={(e) => handleSubjectChange(idx, "exam_date", e.target.value)}
                        style={{ padding: "0.4rem" }}
                      />
                    </td>
                    <td>
                      {subjects.length > 1 && (
                        <button
                          type="button"
                          className="btn btn-secondary btn-sm"
                          onClick={() => removeSubject(idx)}
                          style={{ color: "var(--danger)" }}
                        >
                          ✕
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div style={{ display: "flex", gap: "1rem" }}>
            <button type="button" className="btn btn-secondary" onClick={addSubject}>
              + Add Subject
            </button>
            <button type="submit" className="btn btn-primary" disabled={loading} style={{ flex: 1 }}>
              {loading ? "Generating Schedule..." : "Generate Deterministic Study Plan"}
            </button>
          </div>
        </form>
      </div>

      {/* Generated Schedule Section */}
      {plan && (
        <div>
          {/* Priority Distribution Breakdown */}
          <div className="card">
            <h2 className="card-title">Subject Priority Weightings</h2>
            <div className="form-grid">
              {plan.subjects_weighted?.map((sw, idx) => (
                <div key={idx} style={{ background: "#f8fafc", padding: "1rem", borderRadius: "8px", border: "1px solid var(--border)" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.35rem" }}>
                    <strong>{sw.name}</strong>
                    <span className="badge badge-info">{Math.round((sw.allocated_ratio || 0) * 100)}% Time Share</span>
                  </div>
                  <div style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
                    Difficulty: <strong>{sw.difficulty}</strong> | Score Gap: <strong>{sw.target_score - sw.current_score} pts</strong>
                    {sw.days_left !== null && sw.days_left !== undefined && (
                      <div>Exam in: <strong style={{ color: sw.days_left <= 7 ? "var(--danger)" : "inherit" }}>{sw.days_left} days</strong></div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Schedule Tabs */}
          <div className="card">
            <div style={{ display: "flex", gap: "1rem", borderBottom: "1px solid var(--border)", paddingBottom: "1rem", marginBottom: "1.5rem" }}>
              <button
                type="button"
                className={`btn ${activeTab === "daily" ? "btn-primary" : "btn-secondary"}`}
                onClick={() => setActiveTab("daily")}
              >
                Today's Daily Timetable
              </button>
              <button
                type="button"
                className={`btn ${activeTab === "weekly" ? "btn-primary" : "btn-secondary"}`}
                onClick={() => setActiveTab("weekly")}
              >
                Full Weekly Timetable ({plan.days_planned} Days)
              </button>
            </div>

            {/* Daily View */}
            {activeTab === "daily" && (
              <div>
                <h3 style={{ fontSize: "1.1rem", marginBottom: "1rem", color: "#0f172a" }}>
                  Today's Scheduled Slots ({plan.daily_study_hours} Hours)
                </h3>
                {plan.daily_schedule?.map((slot, idx) => (
                  <div key={idx} className="timetable-slot">
                    <div className="slot-time">
                      🕒 {slot.start_time} - {slot.end_time}
                    </div>
                    <div style={{ flex: 1, padding: "0 1.5rem" }}>
                      <div className="slot-subject">{slot.subject}</div>
                      <div className="slot-activity">{slot.recommended_focus}</div>
                    </div>
                    <div style={{ fontSize: "0.85rem", color: "var(--text-muted)", fontStyle: "italic" }}>
                      Rest: {slot.break_time}
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Weekly View */}
            {activeTab === "weekly" && (
              <div>
                {Object.entries(plan.weekly_schedule || {}).map(([dayKey, slots]) => (
                  <div key={dayKey} style={{ marginBottom: "2rem" }}>
                    <h3 style={{ fontSize: "1.05rem", color: "var(--primary)", borderBottom: "1px solid var(--border)", paddingBottom: "0.5rem" }}>
                      📅 {dayKey}
                    </h3>
                    {slots.map((slot, idx) => (
                      <div
                        key={idx}
                        className="timetable-slot"
                        style={{ opacity: slot.completed ? 0.6 : 1, textDecoration: slot.completed ? "line-through" : "none" }}
                      >
                        <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
                          <input
                            type="checkbox"
                            checked={!!slot.completed}
                            onChange={() => toggleSlotCompleted(dayKey, slot.slot_id)}
                            style={{ width: "18px", height: "18px", cursor: "pointer" }}
                          />
                          <div className="slot-time">
                            {slot.start_time} - {slot.end_time}
                          </div>
                        </div>

                        <div style={{ flex: 1, padding: "0 1.5rem" }}>
                          <div className="slot-subject">{slot.subject}</div>
                          <div className="slot-activity">{slot.recommended_focus}</div>
                        </div>

                        <div style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
                          {slot.break_time}
                        </div>
                      </div>
                    ))}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default StudyPlanner;
