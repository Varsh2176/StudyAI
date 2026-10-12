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
} from "../components/ui";

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

  useEffect(() => {
    const savedEmail = localStorage.getItem("student_email");
    if (!savedEmail) return undefined;

    let cancelled = false;
    const timer = window.setTimeout(() => {
      if (cancelled) return;
      setForm((prev) => ({ ...prev, email: savedEmail }));
      void loadProfileData(savedEmail);
    }, 0);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, []);

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

  const riskBadgeVariant = (level) => {
    const cls = getRiskBadgeClass(level);
    if (cls === "badge-high") return "danger";
    if (cls === "badge-medium") return "warning";
    return "success";
  };

  const predictedScore =
    result?.predicted_exam_score !== undefined && result?.predicted_exam_score !== null
      ? Number(result.predicted_exam_score)
      : null;
  const scoreIsValid = predictedScore !== null && !Number.isNaN(predictedScore);
  const riskLabel =
    result?.risk_assessment?.risk_category || result?.risk_assessment?.risk_level || null;
  const recommendedHours =
    result?.recommended_study_hours ??
    result?.recommended_daily_hours ??
    result?.recommended_weekly_hours ??
    result?.risk_assessment?.recommended_study_hours ??
    null;

  return (
    <div className="sw-forms-page page-container">
      <section className="sw-forms-intro" aria-labelledby="predict-heading">
        <h2 id="predict-heading">Predict exam score & academic risk</h2>
        <p>
          Evaluate expected academic outcome using the trained Ridge Regression pipeline (R² = 0.770, MAE = 0.452)
          and inspect transparent leading risk factors.
        </p>
      </section>

      {profileLoaded ? (
        <div className="sw-forms-info">
          <span>Pre-filled study hours, attendance, and prior scores from your registered profile.</span>
          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={() => loadProfileData(form.email)}
          >
            Re-sync profile
          </Button>
        </div>
      ) : null}

      {error ? (
        <ErrorMessage
          message={typeof error === "string" ? error : "Prediction failed."}
          onRetry={!loading ? () => handleSubmit({ preventDefault() {} }) : undefined}
          retryLabel="Retry prediction"
        />
      ) : null}

      <div
        className={`sw-predict-layout${result ? " sw-predict-layout--split" : ""}`}
      >
        <Card title="Student performance indicators">
          <form onSubmit={handleSubmit}>
            <h3 className="sw-forms-section-title">Core quantitative factors</h3>
            <div className="sw-forms-grid">
              <Input
                label="Weekly study hours (0 - 50) *"
                type="number"
                name="Hours_Studied"
                min="0"
                max="50"
                step="0.5"
                value={form.Hours_Studied}
                onChange={handleChange}
                required
              />
              <Input
                label="Attendance percentage (0 - 100%) *"
                type="number"
                name="Attendance"
                min="0"
                max="100"
                value={form.Attendance}
                onChange={handleChange}
                required
              />
              <Input
                label="Previous exam score (0 - 100%) *"
                type="number"
                name="Previous_Scores"
                min="0"
                max="100"
                value={form.Previous_Scores}
                onChange={handleChange}
                required
              />
              <Input
                label="Daily sleep hours (0 - 24)"
                type="number"
                name="Sleep_Hours"
                min="0"
                max="24"
                step="0.5"
                value={form.Sleep_Hours}
                onChange={handleChange}
                required
              />
              <Input
                label="Monthly tutoring sessions (0 - 20)"
                type="number"
                name="Tutoring_Sessions"
                min="0"
                max="20"
                value={form.Tutoring_Sessions}
                onChange={handleChange}
                required
              />
              <Input
                label="Physical activity hours / week"
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

            <h3 className="sw-forms-section-title">Academic & environmental context</h3>
            <div className="sw-forms-grid">
              <Select
                label="Motivation level"
                name="Motivation_Level"
                value={form.Motivation_Level}
                onChange={handleChange}
              >
                <option value="Low">Low</option>
                <option value="Medium">Medium</option>
                <option value="High">High</option>
              </Select>
              <Select
                label="Teacher quality"
                name="Teacher_Quality"
                value={form.Teacher_Quality}
                onChange={handleChange}
              >
                <option value="Low">Low</option>
                <option value="Medium">Medium</option>
                <option value="High">High</option>
              </Select>
              <Select
                label="Access to resources"
                name="Access_to_Resources"
                value={form.Access_to_Resources}
                onChange={handleChange}
              >
                <option value="Low">Low</option>
                <option value="Medium">Medium</option>
                <option value="High">High</option>
              </Select>
              <Select
                label="Parental involvement"
                name="Parental_Involvement"
                value={form.Parental_Involvement}
                onChange={handleChange}
              >
                <option value="Low">Low</option>
                <option value="Medium">Medium</option>
                <option value="High">High</option>
              </Select>
              <Select
                label="Peer influence"
                name="Peer_Influence"
                value={form.Peer_Influence}
                onChange={handleChange}
              >
                <option value="Negative">Negative</option>
                <option value="Neutral">Neutral</option>
                <option value="Positive">Positive</option>
              </Select>
              <Select
                label="Extracurricular activities"
                name="Extracurricular_Activities"
                value={form.Extracurricular_Activities}
                onChange={handleChange}
              >
                <option value="No">No</option>
                <option value="Yes">Yes</option>
              </Select>
              <Select
                label="Internet access"
                name="Internet_Access"
                value={form.Internet_Access}
                onChange={handleChange}
              >
                <option value="Yes">Yes</option>
                <option value="No">No</option>
              </Select>
              <Select
                label="Learning disabilities"
                name="Learning_Disabilities"
                value={form.Learning_Disabilities}
                onChange={handleChange}
              >
                <option value="No">No</option>
                <option value="Yes">Yes</option>
              </Select>
            </div>

            <Button
              type="submit"
              variant="primary"
              className="sw-register-submit"
              loading={loading}
              disabled={loading}
            >
              {loading ? "Computing ML pipeline prediction..." : "Predict exam score & identify risk"}
            </Button>
          </form>
        </Card>

        {loading && !result ? (
          <div aria-busy="true" aria-label="Computing prediction">
            <Skeleton variant="card" />
            <Skeleton variant="block" />
          </div>
        ) : null}

        {!loading && !result && !error ? (
          <EmptyState
            title="No prediction yet"
            description="Enter performance indicators and run the model to see an estimated exam score and risk assessment."
          />
        ) : null}

        {result ? (
          <Card title="Prediction outcome">
            <div className="sw-predict-score">
              <div className="sw-predict-score-label">Expected exam score</div>
              {scoreIsValid ? (
                <>
                  <div className="sw-predict-score-value">
                    {predictedScore} <span>/ 100</span>
                  </div>
                  <ProgressBar
                    value={Math.min(100, Math.max(0, predictedScore))}
                    label="Predicted score"
                    color="primary"
                  />
                </>
              ) : (
                <p className="sw-forms-note">Predicted score not available in this response.</p>
              )}
            </div>

            {result.model_used || result.metrics ? (
              <div className="sw-predict-metrics">
                {result.model_used ? (
                  <div>
                    <strong>Model pipeline:</strong> {result.model_used}
                  </div>
                ) : null}
                {result.metrics ? (
                  <div>
                    Test MAE: <strong>{result.metrics?.MAE ?? "—"}</strong>
                    {" | "}
                    Test RMSE: <strong>{result.metrics?.RMSE ?? "—"}</strong>
                    {" | "}
                    Test R²: <strong>{result.metrics?.R2 ?? "—"}</strong>
                  </div>
                ) : null}
              </div>
            ) : null}

            {recommendedHours !== null && recommendedHours !== undefined && !Number.isNaN(Number(recommendedHours)) ? (
              <p className="sw-forms-note" style={{ fontStyle: "normal", marginBottom: "1rem" }}>
                Recommended study hours (from API): <strong>{recommendedHours}</strong>
              </p>
            ) : null}

            {result.risk_assessment ? (
              <div>
                <div className="sw-predict-risk-head">
                  <span style={{ fontWeight: 600 }}>Academic risk assessment</span>
                  {riskLabel ? (
                    <Badge variant={riskBadgeVariant(riskLabel)}>{riskLabel}</Badge>
                  ) : (
                    <Badge variant="neutral">Risk not provided</Badge>
                  )}
                </div>

                {result.risk_assessment.concise_explanation ? (
                  <p style={{ fontSize: "var(--sw-text-sm)", color: "var(--sw-text)", marginBottom: "0.75rem" }}>
                    {result.risk_assessment.concise_explanation}
                  </p>
                ) : null}

                {result.risk_assessment.relevant_indicators?.length > 0 ? (
                  <div>
                    <div style={{ fontSize: "var(--sw-text-sm)", fontWeight: 600, marginBottom: "0.35rem" }}>
                      Identified risk indicators
                    </div>
                    <ul className="sw-predict-risk-list">
                      {result.risk_assessment.relevant_indicators.map((ind, i) => (
                        <li key={i}>
                          <strong>
                            {ind.indicator} ({ind.value})
                          </strong>
                          : {ind.message}
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : (
                  <p className="sw-forms-note" style={{ fontStyle: "normal", color: "var(--sw-success)" }}>
                    No adverse academic risk factors detected.
                  </p>
                )}

                {result.risk_assessment.recommended_interventions?.length > 0 ? (
                  <div className="sw-predict-interventions">
                    <strong>Intervention guidance</strong>
                    <ul>
                      {result.risk_assessment.recommended_interventions.map((item, i) => (
                        <li key={i}>{item}</li>
                      ))}
                    </ul>
                  </div>
                ) : null}

                {result.risk_assessment.disclaimer ? (
                  <div className="sw-predict-disclaimer">
                    {result.risk_assessment.disclaimer}
                  </div>
                ) : null}
              </div>
            ) : null}

            <p className="sw-forms-note">
              Predictions are estimates based on the trained model and are not guarantees of actual exam outcomes.
            </p>
          </Card>
        ) : null}
      </div>
    </div>
  );
}

export default PredictScore;
