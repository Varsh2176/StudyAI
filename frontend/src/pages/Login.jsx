import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useAuth } from "../auth/useAuth";
import { getApiUnreachableMessage } from "../services/api";
import { Button, ErrorMessage, Input } from "../components/ui";

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [form, setForm] = useState({ email: "", password: "" });
  const [fieldErrors, setFieldErrors] = useState({});
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

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
    const nextErrors = {};
    if (!form.email.trim()) nextErrors.email = "Enter your email address.";
    else if (!EMAIL_RE.test(form.email.trim())) nextErrors.email = "Enter a valid email address.";
    if (!form.password) nextErrors.password = "Enter your password.";
    setFieldErrors(nextErrors);
    if (Object.keys(nextErrors).length) return;

    setLoading(true);
    try {
      await login({
        email: form.email.trim(),
        password: form.password,
      });
      const next = searchParams.get("next") || "/dashboard";
      navigate(next.startsWith("/") ? next : "/dashboard", { replace: true });
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
            : "Sign in failed. Check your email and password.")
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="sw-register">
      <div className="sw-register-panel">
        <header className="sw-register-header">
          <h1 className="sw-register-card-title">Sign in</h1>
          <p className="sw-register-card-desc">
            Use your StudyWise account. Student data is loaded only for the signed-in email.
          </p>
        </header>

        <form className="sw-register-form" onSubmit={handleSubmit} noValidate>
          <Input
            id="login-email"
            name="email"
            type="email"
            label="Email"
            autoComplete="email"
            value={form.email}
            onChange={handleChange}
            error={fieldErrors.email}
            required
          />
          <Input
            id="login-password"
            name="password"
            type="password"
            label="Password"
            autoComplete="current-password"
            value={form.password}
            onChange={handleChange}
            error={fieldErrors.password}
            required
          />
          {error ? <ErrorMessage message={error} /> : null}
          <Button type="submit" variant="primary" loading={loading} disabled={loading}>
            {loading ? "Signing in…" : "Sign in"}
          </Button>
        </form>

        <p className="sw-register-footer">
          New here? <Link to="/">Create an account</Link>
        </p>
      </div>
    </div>
  );
}

export default Login;
