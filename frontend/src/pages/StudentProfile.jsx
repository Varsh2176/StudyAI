import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import API from "../services/api";
import {
  Button,
  Card,
  ErrorMessage,
  Input,
  Skeleton,
} from "../components/ui";

function StudentProfile() {
  const [form, setForm] = useState({
    email: "",
    age: "",
    course: "",
    year: "",
    branch: "",
    study_hours: "",
    attendance: "",
    previous_cgpa: "",
    subjects: ""
  });

  const [loading, setLoading] = useState(false);
  const [fetching, setFetching] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const fetchExistingProfile = async (emailToFetch) => {
    if (!emailToFetch) return;
    setFetching(true);
    try {
      const res = await API.get(`/student/${emailToFetch}`);
      if (res.data && res.data.course) {
        setForm({
          email: res.data.email || emailToFetch,
          age: res.data.age ?? "",
          course: res.data.course ?? "",
          year: res.data.year ?? "",
          branch: res.data.branch ?? "",
          study_hours: res.data.study_hours ?? "",
          attendance: res.data.attendance ?? "",
          previous_cgpa: res.data.previous_cgpa ?? "",
          subjects: Array.isArray(res.data.subjects) ? res.data.subjects.join(", ") : (res.data.subjects ?? "")
        });
        setMessage("Existing profile loaded successfully!");
      }
    } catch (err) {
      console.log("No profile yet for this email:", err);
    } finally {
      setFetching(false);
    }
  };

  useEffect(() => {
    const savedEmail = localStorage.getItem("student_email");
    if (!savedEmail) return undefined;

    let cancelled = false;
    const timer = window.setTimeout(() => {
      if (cancelled) return;
      setForm((prev) => ({ ...prev, email: savedEmail }));
      void fetchExistingProfile(savedEmail);
    }, 0);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, []);

  const handleChange = (e) => {
    setForm({
      ...form,
      [e.target.name]: e.target.value
    });
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
        subjects: form.subjects
          .split(",")
          .map((subject) => subject.trim())
          .filter(Boolean)
      });

      localStorage.setItem("student_email", form.email);
      setMessage(response.data.message || "Profile saved successfully!");
    } catch (err) {
      console.error(err);
      setError(err.response?.data?.detail || "Failed to save profile. Ensure the backend is reachable.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="sw-forms-page page-container">
      <div className="sw-forms-toolbar">
        <section className="sw-forms-intro" aria-labelledby="profile-heading">
          <h2 id="profile-heading">Student profile</h2>
          <p>
            Configure your academic standing to power predictions and study planning.
          </p>
        </section>
        {form.email ? (
          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={() => fetchExistingProfile(form.email)}
            loading={fetching}
            disabled={fetching}
          >
            {fetching ? "Refreshing..." : "Reload profile"}
          </Button>
        ) : null}
      </div>

      {error ? (
        <ErrorMessage
          message={typeof error === "string" ? error : "Failed to save profile."}
          onRetry={form.email ? () => fetchExistingProfile(form.email) : undefined}
          retryLabel="Reload profile"
        />
      ) : null}

      {message ? (
        <div className="sw-register-success" role="status">
          {message}
        </div>
      ) : null}

      {fetching && !form.course ? (
        <div aria-busy="true" aria-label="Loading profile">
          <Skeleton variant="card" />
          <Skeleton variant="block" />
        </div>
      ) : null}

      <form onSubmit={handleSubmit}>
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

        <Button
          type="submit"
          variant="primary"
          className="sw-register-submit"
          loading={loading}
          disabled={loading}
        >
          {loading ? "Saving profile..." : "Save profile"}
        </Button>
      </form>

      {message ? (
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
