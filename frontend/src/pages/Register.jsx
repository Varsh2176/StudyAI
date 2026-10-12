import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import API from "../services/api";
import { Button, Card, ErrorMessage, Input } from "../components/ui";

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
    <div className="sw-register">
      <Card>
        <h1 className="sw-register-card-title">Student registration</h1>
        <p className="sw-register-card-desc">
          Create your StudyWise AI account to generate adaptive study schedules.
        </p>

        {error ? <ErrorMessage message={error} /> : null}
        {success ? (
          <div className="sw-register-success" role="status">
            {success}
          </div>
        ) : null}

        <form onSubmit={handleSubmit}>
          <Input
            id="register-name"
            label="Full name"
            type="text"
            name="name"
            placeholder="e.g. Alex Johnson"
            value={form.name}
            onChange={handleChange}
            required
            autoComplete="name"
            hint="Your name as used for study records."
          />

          <Input
            id="register-email"
            label="Email address"
            type="email"
            name="email"
            placeholder="student@example.edu"
            value={form.email}
            onChange={handleChange}
            required
            autoComplete="email"
            hint="Used as your student identity across the app."
          />

          <Input
            id="register-password"
            label="Password"
            type="password"
            name="password"
            placeholder="••••••••"
            value={form.password}
            onChange={handleChange}
            required
            autoComplete="new-password"
            hint="Required by the registration API."
          />

          <Button
            type="submit"
            variant="primary"
            className="sw-register-submit"
            loading={loading}
            disabled={loading}
          >
            {loading ? "Registering..." : "Register account"}
          </Button>
        </form>

        <div className="sw-register-footer">
          Already registered?{" "}
          <Link to="/profile">Go to Student Profile →</Link>
        </div>
      </Card>
    </div>
  );
}

export default Register;
