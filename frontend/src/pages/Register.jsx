import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import API from "../services/api";

function Register() {
  const [form, setForm] = useState({
    name: "",
    email: "",
    password: ""
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const navigate = useNavigate();

  const handleChange = (e) => {
    setForm({
      ...form,
      [e.target.name]: e.target.value
    });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setSuccess("");
    setLoading(true);

    try {
      const response = await API.post("/auth/register", form);
      if (response.data.message === "User already exists") {
        setError("A student with this email is already registered. You can proceed directly to your profile.");
        localStorage.setItem("student_email", form.email);
      } else {
        const persistenceWarning =
          response.data.persistence === "memory" || response.data.warning
            ? ` ${response.data.warning || "Saved temporarily in memory only — not persisted to MongoDB."}`
            : "";
        setSuccess(`Registration successful!${persistenceWarning} Redirecting to student profile...`);
        localStorage.setItem("student_email", form.email);
        setTimeout(() => {
          navigate("/profile");
        }, response.data.persistence === "memory" ? 3200 : 1200);
      }
    } catch (err) {
      console.error(err);
      const detail = err.response?.data?.detail;
      const detailText = Array.isArray(detail)
        ? detail.map((d) => d.msg || JSON.stringify(d)).join(" ")
        : typeof detail === "string"
          ? detail
          : "";
      setError(
        detailText ||
          (err.code === "ERR_NETWORK"
            ? "Cannot reach the API. Confirm the backend is running on http://127.0.0.1:8000."
            : "Failed to register. Please ensure backend is running.")
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page-container" style={{ maxWidth: "480px" }}>
      <div className="card">
        <h1 style={{ fontSize: "1.75rem", marginBottom: "0.5rem" }}>Student Registration</h1>
        <p style={{ color: "var(--text-muted)", marginBottom: "1.5rem" }}>
          Create your StudyWise AI account to generate adaptive study schedules.
        </p>

        {error && <div className="alert alert-danger">{error}</div>}
        {success && <div className="alert alert-success">{success}</div>}

        <form onSubmit={handleSubmit}>
          <div className="form-group" style={{ marginBottom: "1rem" }}>
            <label>Full Name</label>
            <input
              type="text"
              name="name"
              placeholder="e.g. Alex Johnson"
              value={form.name}
              onChange={handleChange}
              required
            />
          </div>

          <div className="form-group" style={{ marginBottom: "1rem" }}>
            <label>Email Address</label>
            <input
              type="email"
              name="email"
              placeholder="student@example.edu"
              value={form.email}
              onChange={handleChange}
              required
            />
          </div>

          <div className="form-group" style={{ marginBottom: "1.5rem" }}>
            <label>Password</label>
            <input
              type="password"
              name="password"
              placeholder="••••••••"
              value={form.password}
              onChange={handleChange}
              required
            />
          </div>

          <button type="submit" className="btn btn-primary" style={{ width: "100%" }} disabled={loading}>
            {loading ? "Registering..." : "Register Account"}
          </button>
        </form>

        <div style={{ marginTop: "1.5rem", fontSize: "0.9rem", color: "var(--text-muted)" }}>
          Already registered?{" "}
          <Link to="/profile" style={{ color: "var(--primary)", fontWeight: 600 }}>
            Go to Student Profile →
          </Link>
        </div>
      </div>
    </div>
  );
}

export default Register;