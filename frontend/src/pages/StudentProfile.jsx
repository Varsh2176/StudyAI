import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import API from "../services/api";

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

  useEffect(() => {
    const savedEmail = localStorage.getItem("student_email");
    if (savedEmail) {
      setForm((prev) => ({ ...prev, email: savedEmail }));
      fetchExistingProfile(savedEmail);
    }
  }, []);

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
    <div className="page-container" style={{ maxWidth: "750px" }}>
      <div className="card">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.5rem" }}>
          <div>
            <h1 style={{ fontSize: "1.75rem", margin: 0 }}>Student Profile</h1>
            <p style={{ color: "var(--text-muted)", margin: "0.25rem 0 0 0" }}>
              Configure your academic standing to power predictions and study planning.
            </p>
          </div>
          {form.email && (
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={() => fetchExistingProfile(form.email)}
              disabled={fetching}
            >
              {fetching ? "Refreshing..." : "Reload Profile"}
            </button>
          )}
        </div>

        {error && <div className="alert alert-danger">{error}</div>}
        {message && <div className="alert alert-success">{message}</div>}

        <form onSubmit={handleSubmit}>
          <div className="form-grid">
            <div className="form-group">
              <label>Student Email *</label>
              <input
                name="email"
                type="email"
                placeholder="student@example.edu"
                value={form.email}
                onChange={handleChange}
                required
              />
            </div>

            <div className="form-group">
              <label>Age *</label>
              <input
                name="age"
                type="number"
                placeholder="20"
                value={form.age}
                onChange={handleChange}
                required
              />
            </div>

            <div className="form-group">
              <label>Degree / Course *</label>
              <input
                name="course"
                placeholder="B.Tech Computer Science"
                value={form.course}
                onChange={handleChange}
                required
              />
            </div>

            <div className="form-group">
              <label>Academic Year *</label>
              <input
                name="year"
                type="number"
                placeholder="3"
                value={form.year}
                onChange={handleChange}
                required
              />
            </div>

            <div className="form-group">
              <label>Department / Branch *</label>
              <input
                name="branch"
                placeholder="CSE / AI & ML"
                value={form.branch}
                onChange={handleChange}
                required
              />
            </div>

            <div className="form-group">
              <label>Daily Study Hours *</label>
              <input
                name="study_hours"
                type="number"
                step="0.1"
                placeholder="4.0"
                value={form.study_hours}
                onChange={handleChange}
                required
              />
              <span className="form-help">Typical self-study hours per day</span>
            </div>

            <div className="form-group">
              <label>Attendance Percentage *</label>
              <input
                name="attendance"
                type="number"
                placeholder="85"
                value={form.attendance}
                onChange={handleChange}
                required
              />
              <span className="form-help">Current semester attendance (0 - 100%)</span>
            </div>

            <div className="form-group">
              <label>Previous CGPA / Marks *</label>
              <input
                name="previous_cgpa"
                type="number"
                step="0.01"
                placeholder="8.4"
                value={form.previous_cgpa}
                onChange={handleChange}
                required
              />
              <span className="form-help">Out of 10.0 scale</span>
            </div>
          </div>

          <div className="form-group" style={{ marginBottom: "1.75rem" }}>
            <label>Enrolled Subjects (comma-separated) *</label>
            <input
              name="subjects"
              placeholder="Machine Learning, Data Structures, Operating Systems, Computer Networks"
              value={form.subjects}
              onChange={handleChange}
              required
            />
            <span className="form-help">These subjects will be auto-imported into your personalized study planner</span>
          </div>

          <button type="submit" className="btn btn-primary" disabled={loading} style={{ width: "100%", padding: "0.85rem" }}>
            {loading ? "Saving Profile..." : "Save Profile"}
          </button>
        </form>

        {message && (
          <div style={{ marginTop: "1.75rem", display: "flex", gap: "1rem", justifyContent: "center", flexWrap: "wrap" }}>
            <Link to="/dashboard" className="btn btn-primary">
              Open Dashboard →
            </Link>
            <Link to="/predict" className="btn btn-secondary">
              Predict Exam Score →
            </Link>
            <Link to="/planner" className="btn btn-secondary">
              Generate Study Plan →
            </Link>
          </div>
        )}
      </div>
    </div>
  );
}

export default StudentProfile;