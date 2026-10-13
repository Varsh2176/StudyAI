import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/useAuth";
import { getApiUnreachableMessage } from "../services/api";
import { Button, ErrorMessage, Input } from "../components/ui";

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function validateForm(form) {
  const fieldErrors = {};
  const name = form.name.trim();
  const email = form.email.trim();
  const password = form.password;

  if (!name) {
    fieldErrors.name = "Enter your full name.";
  } else if (name.length < 2) {
    fieldErrors.name = "Name must be at least 2 characters.";
  }

  if (!email) {
    fieldErrors.email = "Enter your email address.";
  } else if (!EMAIL_RE.test(email)) {
    fieldErrors.email = "Enter a valid email address.";
  }

  if (!password) {
    fieldErrors.password = "Enter a password.";
  } else if (password.length < 8) {
    fieldErrors.password = "Password must be at least 8 characters.";
  }

  return fieldErrors;
}

function Register() {
  const { register } = useAuth();
  const [form, setForm] = useState({
    name: "",
    email: "",
    password: "",
  });
  const [fieldErrors, setFieldErrors] = useState({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const navigate = useNavigate();

  const handleChange = (e) => {
    const { name, value } = e.target;
    setForm((prev) => ({ ...prev, [name]: value }));
    if (fieldErrors[name]) {
      setFieldErrors((prev) => {
        const next = { ...prev };
        delete next[name];
        return next;
      });
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setSuccess("");

    const nextFieldErrors = validateForm(form);
    setFieldErrors(nextFieldErrors);
    if (Object.keys(nextFieldErrors).length > 0) {
      return;
    }

    setLoading(true);

    try {
      await register({
        name: form.name.trim(),
        email: form.email.trim(),
        password: form.password,
      });
      setSuccess("Account created. Redirecting to your profile…");
      setTimeout(() => {
        navigate("/profile");
      }, 900);
    } catch (err) {
      const detail = err.response?.data?.detail;
      const detailText = Array.isArray(detail)
        ? detail.map((d) => d.msg || JSON.stringify(d)).join(" ")
        : typeof detail === "string"
          ? detail
          : "";
      setError(
        detailText ||
          (err.code === "ERR_NETWORK"
            ? getApiUnreachableMessage()
            : "Failed to register. Please try again.")
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="sw-register">
      <div className="sw-register-panel">
        <header className="sw-register-header">
          <h1 className="sw-register-card-title">Create your account</h1>
          <p className="sw-register-card-desc">
            Register with a unique email and password. After sign-in, StudyWise uses your
            authenticated account to protect your profiles, documents, and progress.
          </p>
        </header>

        {error ? <ErrorMessage message={error} /> : null}
        {success ? (
          <div className="sw-register-success" role="status">
            {success}
          </div>
        ) : null}

        <form className="sw-register-form" onSubmit={handleSubmit} noValidate>
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
            error={fieldErrors.name}
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
            error={fieldErrors.email}
            hint={fieldErrors.email ? undefined : "This becomes your signed-in account identity."}
          />

          <Input
            id="register-password"
            label="Password"
            type="password"
            name="password"
            placeholder="At least 8 characters"
            value={form.password}
            onChange={handleChange}
            required
            autoComplete="new-password"
            error={fieldErrors.password}
            hint={
              fieldErrors.password
                ? undefined
                : "Stored as a secure hash on the server — never in the browser."
            }
          />

          <Button
            type="submit"
            variant="primary"
            className="sw-register-submit"
            loading={loading}
            disabled={loading}
          >
            {loading ? "Creating account…" : "Create account"}
          </Button>
        </form>

        <div className="sw-register-footer">
          Already registered? <Link to="/login">Sign in</Link>
        </div>
      </div>
    </div>
  );
}

export default Register;
