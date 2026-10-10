import { useState, useEffect } from "react";
import API from "../services/api";

function PredictScore() {
  const [form, setForm] = useState({
    Hours_Studied: 15,
    Attendance: 85,
    Sleep_Hours: 7.0,
    Previous_Scores: 75,
    Tutoring_Sessions: 1,
    Physical_Activity: 3.0,
    Parental_Involvement: "Medium",
    Access_to_Resources: "Medium",
    Extracurricular_Activities: "No",
    Motivation_Level: "Medium",
    Internet_Access: "Yes",
    Family_Income: "Medium",
    Teacher_Quality: "Medium",
    School_Type: "Public",
    Peer_Influence: "Neutral",
    Learning_Disabilities: "No",
    Parental_Education_Level: "College",
    Distance_from_Home: "Moderate",
    Gender: "Female",
    email: ""
  });

  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [profileLoaded, setProfileLoaded] = useState(false);

  useEffect(() => {
    const savedEmail = localStorage.getItem("student_email");
    if (savedEmail) {
      setForm((prev) => ({ ...prev, email: savedEmail }));
      loadProfileData(savedEmail);
    }
  }, []);

  const loadProfileData = async (emailToFetch) => {
    try {
      const res = await API.get(`/student/${emailToFetch}`);
      if (res.data && res.data.attendance !== undefined) {
        setForm((prev) => ({
          ...prev,
          email: emailToFetch,
          Attendance: Number(res.data.attendance) || prev.Attendance,
          // Convert daily study hours to estimated weekly hours (daily * 5)
          Hours_Studied: Math.min(50, Math.max(1, Math.round((Number(res.data.study_hours) || 3) * 5))),
          // Convert 10-point CGPA to 100-point percentage scale
          Previous_Scores: Math.min(100, Math.max(0, Math.round((Number(res.data.previous_cgpa) || 7.5) * 10)))
        }));
        setProfileLoaded(true);
      }
    } catch (err) {
      console.log("Could not auto-populate from profile:", err);
    }
  };

  const handleChange = (e) => {
    const { name, value, type } = e.target;
    setForm({
      ...form,
      [name]: type === "number" ? Number(value) : value
    });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setResult(null);
    setLoading(true);

    try {
      const response = await API.post("/predict/exam-score", form);
      setResult(response.data);
    } catch (err) {
      console.error(err);
      setError(
        err.response?.data?.detail ||
        "Failed to compute prediction. Make sure backend is running and model is trained."
      );
    } finally {
      setLoading(false);
    }
  };

  const getRiskBadgeClass = (level) => {
    if (level === "High Risk") return "badge-high";
    if (level === "Moderate Risk" || level === "Medium Risk") return "badge-medium";
    return "badge-low";
  };

  return (
    <div className="page-container">
      <div className="page-header">
        <h1>Predict Exam Score & Academic Risk</h1>
        <p>
          Evaluate expected academic outcome using the trained Ridge Regression pipeline (R² = 0.770, MAE = 0.452)
          and inspect transparent leading risk factors.
        </p>
      </div>

      {profileLoaded && (
        <div className="alert alert-info" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span>✓ Pre-filled study hours, attendance, and prior scores from your registered profile.</span>
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={() => loadProfileData(form.email)}
          >
            Re-sync Profile
          </button>
        </div>
      )}

      {error && <div className="alert alert-danger">{error}</div>}

      <div style={{ display: "grid", gridTemplateColumns: result ? "1.1fr 0.9fr" : "1fr", gap: "2rem" }}>
        {/* Form Card */}
        <div className="card">
          <h2 className="card-title">Student Performance Indicators</h2>

          <form onSubmit={handleSubmit}>
            <h3 style={{ fontSize: "1rem", color: "var(--primary)", marginTop: 0 }}>Core Quantitative Factors</h3>
            <div className="form-grid">
              <div className="form-group">
                <label>Weekly Study Hours (0 - 50) *</label>
                <input
                  type="number"
                  name="Hours_Studied"
                  min="0"
                  max="50"
                  step="0.5"
                  value={form.Hours_Studied}
                  onChange={handleChange}
                  required
                />
              </div>

              <div className="form-group">
                <label>Attendance Percentage (0 - 100%) *</label>
                <input
                  type="number"
                  name="Attendance"
                  min="0"
                  max="100"
                  value={form.Attendance}
                  onChange={handleChange}
                  required
                />
              </div>

              <div className="form-group">
                <label>Previous Exam Score (0 - 100%) *</label>
                <input
                  type="number"
                  name="Previous_Scores"
                  min="0"
                  max="100"
                  value={form.Previous_Scores}
                  onChange={handleChange}
                  required
                />
              </div>

              <div className="form-group">
                <label>Daily Sleep Hours (0 - 24)</label>
                <input
                  type="number"
                  name="Sleep_Hours"
                  min="0"
                  max="24"
                  step="0.5"
                  value={form.Sleep_Hours}
                  onChange={handleChange}
                  required
                />
              </div>

              <div className="form-group">
                <label>Monthly Tutoring Sessions (0 - 20)</label>
                <input
                  type="number"
                  name="Tutoring_Sessions"
                  min="0"
                  max="20"
                  value={form.Tutoring_Sessions}
                  onChange={handleChange}
                  required
                />
              </div>

              <div className="form-group">
                <label>Physical Activity Hours / Week</label>
                <input
                  type="number"
                  name="Physical_Activity"
                  min="0"
                  max="20"
                  step="0.5"
                  value={form.Physical_Activity}
                  onChange={handleChange}
                  required
                />
              </div>
            </div>

            <h3 style={{ fontSize: "1rem", color: "var(--primary)", marginTop: "1rem" }}>Academic & Environmental Context</h3>
            <div className="form-grid">
              <div className="form-group">
                <label>Motivation Level</label>
                <select name="Motivation_Level" value={form.Motivation_Level} onChange={handleChange}>
                  <option value="Low">Low</option>
                  <option value="Medium">Medium</option>
                  <option value="High">High</option>
                </select>
              </div>

              <div className="form-group">
                <label>Teacher Quality</label>
                <select name="Teacher_Quality" value={form.Teacher_Quality} onChange={handleChange}>
                  <option value="Low">Low</option>
                  <option value="Medium">Medium</option>
                  <option value="High">High</option>
                </select>
              </div>

              <div className="form-group">
                <label>Access to Resources</label>
                <select name="Access_to_Resources" value={form.Access_to_Resources} onChange={handleChange}>
                  <option value="Low">Low</option>
                  <option value="Medium">Medium</option>
                  <option value="High">High</option>
                </select>
              </div>

              <div className="form-group">
                <label>Parental Involvement</label>
                <select name="Parental_Involvement" value={form.Parental_Involvement} onChange={handleChange}>
                  <option value="Low">Low</option>
                  <option value="Medium">Medium</option>
                  <option value="High">High</option>
                </select>
              </div>

              <div className="form-group">
                <label>Peer Influence</label>
                <select name="Peer_Influence" value={form.Peer_Influence} onChange={handleChange}>
                  <option value="Negative">Negative</option>
                  <option value="Neutral">Neutral</option>
                  <option value="Positive">Positive</option>
                </select>
              </div>

              <div className="form-group">
                <label>Extracurricular Activities</label>
                <select name="Extracurricular_Activities" value={form.Extracurricular_Activities} onChange={handleChange}>
                  <option value="No">No</option>
                  <option value="Yes">Yes</option>
                </select>
              </div>

              <div className="form-group">
                <label>Internet Access</label>
                <select name="Internet_Access" value={form.Internet_Access} onChange={handleChange}>
                  <option value="Yes">Yes</option>
                  <option value="No">No</option>
                </select>
              </div>

              <div className="form-group">
                <label>Learning Disabilities</label>
                <select name="Learning_Disabilities" value={form.Learning_Disabilities} onChange={handleChange}>
                  <option value="No">No</option>
                  <option value="Yes">Yes</option>
                </select>
              </div>
            </div>

            <button type="submit" className="btn btn-primary" style={{ width: "100%", padding: "0.85rem" }} disabled={loading}>
              {loading ? "Computing ML Pipeline Prediction..." : "Predict Exam Score & Identify Risk"}
            </button>
          </form>
        </div>

        {/* Prediction Results Card */}
        {result && (
          <div>
            <div className="card" style={{ borderTop: "4px solid var(--primary)" }}>
              <h2 className="card-title">Prediction Outcome</h2>
              
              <div style={{ textAlign: "center", padding: "1.5rem 0" }}>
                <div style={{ fontSize: "0.9rem", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                  Expected Exam Score
                </div>
                <div style={{ fontSize: "3.5rem", fontWeight: 800, color: "var(--primary)", lineHeight: 1.2 }}>
                  {result.predicted_exam_score} <span style={{ fontSize: "1.5rem", color: "var(--text-muted)" }}>/ 100</span>
                </div>
                <div className="progress-bar-container" style={{ maxWidth: "260px", margin: "1rem auto 0" }}>
                  <div className="progress-bar-fill" style={{ width: `${Math.min(100, result.predicted_exam_score)}%` }}></div>
                </div>
              </div>

              {/* Model Info Badge */}
              <div style={{ background: "#f8fafc", padding: "1rem", borderRadius: "8px", marginBottom: "1.25rem", fontSize: "0.85rem" }}>
                <div style={{ fontWeight: 600, color: "#1e293b", marginBottom: "0.25rem" }}>
                  Model Pipeline: {result.model_used}
                </div>
                <div style={{ color: "var(--text-muted)" }}>
                  Test MAE: <strong>{result.metrics?.MAE}</strong> | Test RMSE: <strong>{result.metrics?.RMSE}</strong> | Test R²: <strong>{result.metrics?.R2}</strong>
                </div>
              </div>

              {/* Phase E Risk Assessment */}
              {result.risk_assessment && (
                <div style={{ borderTop: "1px solid var(--border)", paddingTop: "1.25rem" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem" }}>
                    <span style={{ fontWeight: 600, fontSize: "1rem" }}>Academic Risk Assessment:</span>
                    <span className={`badge ${getRiskBadgeClass(result.risk_assessment.risk_category || result.risk_assessment.risk_level)}`}>
                      {result.risk_assessment.risk_category || result.risk_assessment.risk_level}
                    </span>
                  </div>

                  {result.risk_assessment.concise_explanation && (
                    <p style={{ fontSize: "0.9rem", color: "#334155", marginBottom: "0.75rem" }}>
                      {result.risk_assessment.concise_explanation}
                    </p>
                  )}

                  {result.risk_assessment.relevant_indicators?.length > 0 ? (
                    <div style={{ marginBottom: "0.75rem" }}>
                      <div style={{ fontSize: "0.85rem", fontWeight: 600, color: "#475569", marginBottom: "0.35rem" }}>
                        Identified Risk Indicators:
                      </div>
                      <ul style={{ margin: 0, paddingLeft: "1.25rem", fontSize: "0.85rem", color: "#64748b" }}>
                        {result.risk_assessment.relevant_indicators.map((ind, i) => (
                          <li key={i}>
                            <strong>{ind.indicator} ({ind.value})</strong>: {ind.message}
                          </li>
                        ))}
                      </ul>
                    </div>
                  ) : (
                    <p style={{ fontSize: "0.85rem", color: "var(--success)", marginBottom: "0.75rem" }}>
                      ✓ No adverse academic risk factors detected.
                    </p>
                  )}

                  {result.risk_assessment.recommended_interventions?.length > 0 && (
                    <div style={{ background: "var(--primary-light)", padding: "0.85rem", borderRadius: "6px", fontSize: "0.85rem", color: "#312e81", marginBottom: "0.75rem" }}>
                      <strong>Intervention Guidance:</strong>
                      <ul style={{ margin: "0.35rem 0 0 0", paddingLeft: "1.2rem" }}>
                        {result.risk_assessment.recommended_interventions.map((item, i) => (
                          <li key={i}>{item}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {result.risk_assessment.disclaimer && (
                    <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", fontStyle: "italic", marginTop: "0.5rem" }}>
                      ℹ {result.risk_assessment.disclaimer}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default PredictScore;
