import { useState, useEffect, useCallback } from "react";
import { Link } from "react-router-dom";
import API from "../services/api";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorMessage,
  Input,
  Skeleton,
} from "../components/ui";

const EMPTY_FORM = {
  email: "",
  age: "",
  course: "",
  year: "",
  branch: "",
  study_hours: "",
  attendance: "",
  previous_cgpa: "",
  subjects: "",
};

function profileToForm(data, fallbackEmail = "") {
  return {
    email: data.email || fallbackEmail,
    age: data.age ?? "",
    course: data.course ?? "",
    year: data.year ?? "",
    branch: data.branch ?? "",
    study_hours: data.study_hours ?? "",
    attendance: data.attendance ?? "",
    previous_cgpa: data.previous_cgpa ?? "",
    subjects: Array.isArray(data.subjects)
      ? data.subjects.join(", ")
      : (data.subjects ?? ""),
  };
}

function subjectsList(subjectsStr) {
  return String(subjectsStr || "")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
}

function StudentProfile() {
  const [form, setForm] = useState(EMPTY_FORM);
  const [snapshot, setSnapshot] = useState(EMPTY_FORM);
  const [editing, setEditing] = useState(true);
  const [hasSavedProfile, setHasSavedProfile] = useState(false);
  const [loading, setLoading] = useState(false);
  const [fetching, setFetching] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const fetchExistingProfile = useCallback(async (emailToFetch) => {
    if (!emailToFetch) return;
    setFetching(true);
    setError("");
    try {
      const res = await API.get(`/student/${emailToFetch}`);
      if (res.data && res.data.course) {
        const next = profileToForm(res.data, emailToFetch);
        setForm(next);
        setSnapshot(next);
        setHasSavedProfile(true);
        setEditing(false);
        setMessage("Existing profile loaded successfully!");
      } else {
        setHasSavedProfile(false);
        setEditing(true);
      }
    } catch (err) {
      console.log("No profile yet for this email:", err);
      setHasSavedProfile(false);
      setEditing(true);
    } finally {
      setFetching(false);
    }
  }, []);

  useEffect(() => {
    const savedEmail = localStorage.getItem("student_email");
    if (!savedEmail) return undefined;

    let cancelled = false;
    const timer = window.setTimeout(() => {
      if (cancelled) return;
      setForm((prev) => ({ ...prev, email: savedEmail }));
      setSnapshot((prev) => ({ ...prev, email: savedEmail }));
      void fetchExistingProfile(savedEmail);
    }, 0);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [fetchExistingProfile]);

  const handleChange = (e) => {
    setForm({
      ...form,
      [e.target.name]: e.target.value,
    });
  };

  const handleEdit = () => {
    setSnapshot(form);
    setEditing(true);
    setMessage("");
    setError("");
  };

  const handleCancel = () => {
    setForm(snapshot);
    setEditing(false);
    setMessage("");
    setError("");
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setMessage("");
    setError("");
    setLoading(true);

    try {
      const response = await API.post("/student/profile", {
        email: form.email,
        age: Number(form.age),
        course: form.course,
        year: Number(form.year),
        branch: form.branch,
        study_hours: Number(form.study_hours),
        attendance: Number(form.attendance),
        previous_cgpa: Number(form.previous_cgpa),
        subjects: subjectsList(form.subjects),
      });

      localStorage.setItem("student_email", form.email);
      window.dispatchEvent(new Event("studyai-identity-changed"));
      setSnapshot(form);
      setHasSavedProfile(true);
      setEditing(false);
      setMessage(response.data.message || "Profile saved successfully!");
    } catch (err) {
      console.error(err);
      setError(
        err.response?.data?.detail ||
          "Failed to save profile. Ensure the backend is reachable."
      );
    } finally {
      setLoading(false);
    }
  };

  const subjectChips = subjectsList(form.subjects);

  return (
    <div className="sw-forms-page sw-profile-page page-container">
      <div className="sw-forms-hero">
        <div className="sw-forms-toolbar">
          <section className="sw-forms-intro" aria-labelledby="profile-heading">
            <p className="sw-forms-eyebrow">Academic identity</p>
            <h2 id="profile-heading">Student profile</h2>
            <p>
              Configure your academic standing so score predictions and study
              plans use your real course, availability, and subject list.
            </p>
          </section>
          <div className="sw-forms-toolbar-actions">
            {form.email ? (
              <Button
                type="button"
                variant="secondary"
                size="sm"
                onClick={() => fetchExistingProfile(form.email)}
                loading={fetching}
                disabled={fetching || loading}
              >
                {fetching ? "Refreshing…" : "Reload profile"}
              </Button>
            ) : null}
            {hasSavedProfile && !editing ? (
              <Button type="button" variant="primary" size="sm" onClick={handleEdit}>
                Edit profile
              </Button>
            ) : null}
          </div>
        </div>
      </div>

      {error ? (
        <ErrorMessage
          message={typeof error === "string" ? error : "Failed to save profile."}
          onRetry={form.email ? () => fetchExistingProfile(form.email) : undefined}
          retryLabel="Reload profile"
        />
      ) : null}

      {message ? (
        <div className="sw-forms-success" role="status">
          {message}
        </div>
      ) : null}

      {fetching && !form.course ? (
        <div aria-busy="true" aria-label="Loading profile">
          <Skeleton variant="card" />
          <Skeleton variant="block" />
        </div>
      ) : null}

      {!form.email && !fetching ? (
        <EmptyState
          title="No student email yet"
          description="Register first, or enter your student email in the form below to create a profile."
          action={
            <Link to="/" className="sw-btn sw-btn--secondary sw-btn--sm">
              Go to Registration
            </Link>
          }
        />
      ) : null}

      {hasSavedProfile && !editing ? (
        <Card title="Saved student information" className="sw-forms-section sw-profile-summary">
          <div className="sw-profile-summary-grid">
            <div>
              <span className="sw-profile-label">Email</span>
              <span className="sw-profile-value">{form.email || "—"}</span>
            </div>
            <div>
              <span className="sw-profile-label">Age</span>
              <span className="sw-profile-value">{form.age !== "" ? form.age : "—"}</span>
            </div>
            <div>
              <span className="sw-profile-label">Course</span>
              <span className="sw-profile-value">{form.course || "—"}</span>
            </div>
            <div>
              <span className="sw-profile-label">Year</span>
              <span className="sw-profile-value">{form.year !== "" ? form.year : "—"}</span>
            </div>
            <div>
              <span className="sw-profile-label">Branch</span>
              <span className="sw-profile-value">{form.branch || "—"}</span>
            </div>
            <div>
              <span className="sw-profile-label">Study hours</span>
              <span className="sw-profile-value">
                {form.study_hours !== "" ? `${form.study_hours} hrs/day` : "—"}
              </span>
            </div>
            <div>
              <span className="sw-profile-label">Attendance</span>
              <span className="sw-profile-value">
                {form.attendance !== "" ? `${form.attendance}%` : "—"}
              </span>
            </div>
            <div>
              <span className="sw-profile-label">Previous CGPA</span>
              <span className="sw-profile-value">
                {form.previous_cgpa !== "" ? form.previous_cgpa : "—"}
              </span>
            </div>
            <div className="sw-profile-summary-subjects">
              <span className="sw-profile-label">Subjects</span>
              <div className="sw-profile-chip-row">
                {subjectChips.length > 0 ? (
                  subjectChips.map((subject) => (
                    <Badge key={subject} variant="primary">
                      {subject}
                    </Badge>
                  ))
                ) : (
                  <span className="sw-profile-value">None listed</span>
                )}
              </div>
            </div>
          </div>
        </Card>
      ) : null}

      {editing ? (
        <form className="sw-profile-form" onSubmit={handleSubmit}>
          <Card title="Personal details" className="sw-forms-section">
            <div className="sw-forms-grid">
              <Input
                label="Student email *"
                name="email"
                type="email"
                placeholder="student@example.edu"
                value={form.email}
                onChange={handleChange}
                required
                autoComplete="email"
                hint="Used as your student identity across StudyWise AI."
              />
              <Input
                label="Age *"
                name="age"
                type="number"
                placeholder="20"
                value={form.age}
                onChange={handleChange}
                required
              />
            </div>
          </Card>

          <Card title="Academic details" className="sw-forms-section">
            <div className="sw-forms-grid">
              <Input
                label="Degree / course *"
                name="course"
                placeholder="B.Tech Computer Science"
                value={form.course}
                onChange={handleChange}
                required
              />
              <Input
                label="Academic year *"
                name="year"
                type="number"
                placeholder="3"
                value={form.year}
                onChange={handleChange}
                required
              />
              <Input
                label="Department / branch *"
                name="branch"
                placeholder="CSE / AI & ML"
                value={form.branch}
                onChange={handleChange}
                required
              />
            </div>
            <Input
              label="Enrolled subjects (comma-separated) *"
              name="subjects"
              placeholder="Machine Learning, Data Structures, Operating Systems, Computer Networks"
              value={form.subjects}
              onChange={handleChange}
              required
              hint="These subjects will be auto-imported into your personalized study planner"
            />
          </Card>

          <Card title="Study preferences" className="sw-forms-section">
            <div className="sw-forms-grid">
              <Input
                label="Daily study hours *"
                name="study_hours"
                type="number"
                step="0.1"
                placeholder="4.0"
                value={form.study_hours}
                onChange={handleChange}
                required
                hint="Typical self-study hours per day"
              />
              <Input
                label="Attendance percentage *"
                name="attendance"
                type="number"
                placeholder="85"
                value={form.attendance}
                onChange={handleChange}
                required
                hint="Current semester attendance (0 - 100%)"
              />
              <Input
                label="Previous CGPA / marks *"
                name="previous_cgpa"
                type="number"
                step="0.01"
                placeholder="8.4"
                value={form.previous_cgpa}
                onChange={handleChange}
                required
                hint="Out of 10.0 scale"
              />
            </div>
          </Card>

          <div className="sw-forms-footer-actions">
            {hasSavedProfile ? (
              <Button
                type="button"
                variant="secondary"
                onClick={handleCancel}
                disabled={loading}
              >
                Cancel
              </Button>
            ) : null}
            <Button
              type="submit"
              variant="primary"
              className="sw-forms-submit"
              loading={loading}
              disabled={loading}
            >
              {loading ? "Saving profile…" : "Save profile"}
            </Button>
          </div>
        </form>
      ) : null}

      {message && hasSavedProfile && !editing ? (
        <div className="sw-forms-actions">
          <Link to="/dashboard" className="sw-btn sw-btn--primary sw-btn--md">
            Open Dashboard →
          </Link>
          <Link to="/predict" className="sw-btn sw-btn--secondary sw-btn--md">
            Predict Exam Score →
          </Link>
          <Link to="/planner" className="sw-btn sw-btn--secondary sw-btn--md">
            Generate Study Plan →
          </Link>
        </div>
      ) : null}
    </div>
  );
}

export default StudentProfile;
