import { NavLink } from "react-router-dom";
import {
  IconDashboard,
  IconDocuments,
  IconHub,
  IconPlanner,
  IconPredict,
  IconProfile,
  IconProgress,
  IconTutor,
} from "./ui/Icons";

/**
 * App navigation links.
 * Used as the sidebar / drawer nav (variant="sidebar").
 * Register stays on the auth layout, not in this list.
 */
const APP_LINKS = [
  { to: "/dashboard", label: "Dashboard", Icon: IconDashboard },
  { to: "/hub", label: "Learning Hub", Icon: IconHub },
  { to: "/predict", label: "Predict", Icon: IconPredict },
  { to: "/planner", label: "Planner", Icon: IconPlanner },
  { to: "/tutor", label: "AI Tutor", Icon: IconTutor },
  { to: "/documents", label: "Documents", Icon: IconDocuments },
  { to: "/progress", label: "Progress", Icon: IconProgress },
  { to: "/profile", label: "Profile", Icon: IconProfile },
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
        {APP_LINKS.map((link) => {
          const Icon = link.Icon;
          return (
            <NavLink
              key={link.to}
              to={link.to}
              className={({ isActive }) =>
                `nav-link ${isActive ? "active" : ""}`
              }
              onClick={() => {
                if (typeof onNavigate === "function") onNavigate();
              }}
            >
              <span className="nav-link-icon" aria-hidden="true">
                <Icon size={18} />
              </span>
              <span className="nav-link-label">{link.label}</span>
            </NavLink>
          );
        })}
      </div>
    </nav>
  );
}

export default Navbar;
