import { NavLink } from "react-router-dom";

/**
 * App navigation links.
 * Phase 1: used as the sidebar / drawer nav (variant="sidebar").
 * Register stays on the auth layout, not in this list.
 */
const APP_LINKS = [
  { to: "/dashboard", label: "Dashboard" },
  { to: "/predict", label: "Predict" },
  { to: "/planner", label: "Planner" },
  { to: "/tutor", label: "AI Tutor" },
  { to: "/documents", label: "Documents" },
  { to: "/progress", label: "Progress" },
  { to: "/profile", label: "Profile" },
];

function Navbar({ variant = "sidebar", onNavigate, navId = "sw-sidebar-nav" }) {
  const isSidebar = variant === "sidebar";

  return (
    <nav
      className={isSidebar ? "navbar navbar-sidebar" : "navbar"}
      aria-label="Main"
      id={navId}
    >
      {!isSidebar && (
        <NavLink to="/dashboard" className="nav-brand">
          StudyWise AI
        </NavLink>
      )}
      <div className="nav-links">
        {APP_LINKS.map((link) => (
          <NavLink
            key={link.to}
            to={link.to}
            className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}
            onClick={() => {
              if (typeof onNavigate === "function") onNavigate();
            }}
          >
            {link.label}
          </NavLink>
        ))}
      </div>
    </nav>
  );
}

export default Navbar;
