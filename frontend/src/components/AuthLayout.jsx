import { Link, Outlet } from "react-router-dom";

/**
 * Layout for unauthenticated/auth screens (Register at "/").
 * Slim top bar with brand only — no sidebar.
 */
function AuthLayout() {
  return (
    <div className="app-container">
      <header className="auth-topbar">
        <Link to="/" className="auth-topbar-brand">
          StudyWise AI
        </Link>
      </header>
      <main className="auth-layout-main" id="main-content">
        <Outlet />
      </main>
    </div>
  );
}

export default AuthLayout;
