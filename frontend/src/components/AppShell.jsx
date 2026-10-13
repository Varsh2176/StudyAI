import { useCallback, useEffect, useId, useRef, useState } from "react";
import { Link, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/useAuth";
import Navbar from "./Navbar";
import { Button, Modal } from "./ui";
import { IconClose, IconMenu } from "./ui/Icons";
import { ThemeSelector } from "../theme";

const PAGE_TITLES = {
  "/dashboard": "Dashboard",
  "/hub": "AI Learning Hub",
  "/hub/summary": "Summary Notes",
  "/hub/flashcards": "Flashcards",
  "/hub/mindmap": "Mind Maps",
  "/hub/practice": "Practice Questions",
  "/hub/mock-exam": "Mock Exams",
  "/predict": "Predict Score & Risk",
  "/planner": "Study Planner",
  "/tutor": "AI Tutor",
  "/documents": "Documents",
  "/progress": "Progress",
  "/profile": "Student Profile",
};

const PAGE_SUBTITLES = {
  "/dashboard": "Your study overview and saved insights",
  "/hub": "Discover and open study tools",
  "/hub/summary": "Topic or notes-based study summaries",
  "/hub/flashcards": "Active recall cards from the AI Tutor",
  "/hub/mindmap": "Concept hierarchy from the AI Tutor",
  "/hub/practice": "Topic drills with revealable answers",
  "/hub/mock-exam": "Short generated practice assessments",
  "/predict": "Exam score prediction and academic risk",
  "/planner": "Adaptive schedules from your profile and risk",
  "/tutor": "Ask questions grounded in your materials",
  "/documents": "Upload, index, and manage study PDFs",
  "/progress": "Track planned versus completed study work",
  "/profile": "Academic background used across StudyWise",
};

function titleForPath(pathname) {
  return PAGE_TITLES[pathname] || "StudyWise AI";
}

function subtitleForPath(pathname) {
  return PAGE_SUBTITLES[pathname] || "";
}

/**
 * App chrome: fixed sidebar (desktop), accessible mobile drawer, sticky header.
 * Switch Student clears only localStorage.student_email — no backend call.
 */
function AppShell() {
  const location = useLocation();
  const navigate = useNavigate();
  const { email: studentEmail, name: studentName, logout } = useAuth();
  const [drawerKey, setDrawerKey] = useState(null);
  const [logoutOpen, setLogoutOpen] = useState(false);
  const [loggingOut, setLoggingOut] = useState(false);
  const drawerOpen = drawerKey === location.key;
  const toggleRef = useRef(null);
  const sidebarRef = useRef(null);
  const sidebarId = useId();
  const navId = `${sidebarId}-nav`;

  const closeDrawer = useCallback(() => {
    setDrawerKey(null);
  }, []);

  const toggleDrawer = useCallback(() => {
    setDrawerKey((current) => (current === location.key ? null : location.key));
  }, [location.key]);


  useEffect(() => {
    if (drawerOpen) {
      document.body.classList.add("sw-drawer-lock");
    } else {
      document.body.classList.remove("sw-drawer-lock");
    }
    return () => {
      document.body.classList.remove("sw-drawer-lock");
    };
  }, [drawerOpen]);

  useEffect(() => {
    if (!drawerOpen) return undefined;

    const sidebar = sidebarRef.current;
    const toggleEl = toggleRef.current;

    const focusables = sidebar
      ? sidebar.querySelectorAll(
          'a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])'
        )
      : [];
    if (focusables.length > 0) {
      focusables[0].focus();
    } else if (sidebar) {
      sidebar.focus();
    }

    const onKeyDown = (event) => {
      if (event.key === "Escape") {
        event.preventDefault();
        setDrawerKey(null);
      }
    };
    document.addEventListener("keydown", onKeyDown);

    return () => {
      document.removeEventListener("keydown", onKeyDown);
      if (toggleEl) {
        toggleEl.focus();
      }
    };
  }, [drawerOpen]);

  const confirmLogout = async () => {
    setLoggingOut(true);
    try {
      await logout();
      setLogoutOpen(false);
      setDrawerKey(null);
      navigate("/login", { replace: true });
    } finally {
      setLoggingOut(false);
    }
  };

  const pageTitle = titleForPath(location.pathname);
  const pageSubtitle = subtitleForPath(location.pathname);

  return (
    <div className={`sw-shell${drawerOpen ? " sw-drawer-open" : ""}`}>
      {drawerOpen ? (
        <button
          type="button"
          className="sw-drawer-backdrop"
          aria-label="Close navigation menu"
          onClick={closeDrawer}
        />
      ) : null}

      <aside
        ref={sidebarRef}
        id={sidebarId}
        className="sw-sidebar"
        aria-label="Application"
        tabIndex={-1}
      >
        <div className="sw-sidebar-top">
          <Link to="/dashboard" className="sw-sidebar-brand" onClick={closeDrawer}>
            <span className="sw-sidebar-mark" aria-hidden="true">
              SW
            </span>
            <span className="sw-sidebar-brand-text">
              <span className="sw-sidebar-brand-name">StudyWise AI</span>
              <span className="sw-sidebar-brand-tag">Study platform</span>
            </span>
          </Link>
          <button
            type="button"
            className="sw-sidebar-close"
            aria-label="Close navigation menu"
            onClick={closeDrawer}
          >
            <IconClose size={18} />
          </button>
        </div>

        <p className="sw-sidebar-section-label" id={`${navId}-label`}>
          Navigate
        </p>
        <div className="sw-sidebar-nav">
          <Navbar variant="sidebar" navId={navId} onNavigate={closeDrawer} />
        </div>

        <div className="sw-sidebar-footer">
          {studentEmail ? (
            <div className="sw-sidebar-student" title={studentEmail}>
              <span className="sw-sidebar-student-label">
                {studentName ? studentName : "Signed in"}
              </span>
              <span className="sw-sidebar-student-email">{studentEmail}</span>
            </div>
          ) : (
            <div className="sw-sidebar-student sw-sidebar-student--empty">
              <span className="sw-sidebar-student-label">Not signed in</span>
              <Link to="/login" className="sw-sidebar-student-link" onClick={closeDrawer}>
                Sign in
              </Link>
            </div>
          )}
        </div>
      </aside>

      <div className="sw-shell-main">
        <header className="sw-top-header">
          <button
            ref={toggleRef}
            type="button"
            className="sw-menu-toggle"
            aria-expanded={drawerOpen}
            aria-controls={sidebarId}
            aria-label={drawerOpen ? "Close navigation menu" : "Open navigation menu"}
            onClick={toggleDrawer}
          >
            <IconMenu size={20} />
          </button>

          <div className="sw-page-heading">
            <h1 className="sw-page-title">{pageTitle}</h1>
            {pageSubtitle ? (
              <p className="sw-page-subtitle">{pageSubtitle}</p>
            ) : null}
          </div>

          <div className="sw-header-actions">
            {studentEmail ? (
              <span className="sw-header-student" title={studentEmail}>
                {studentEmail}
              </span>
            ) : null}
            <ThemeSelector size="sm" />
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={() => setLogoutOpen(true)}
            >
              Sign out
            </Button>
          </div>
        </header>

        <main className="sw-shell-content" id="main-content">
          <Outlet />
        </main>
      </div>

      <Modal
        open={logoutOpen}
        title="Sign out?"
        onClose={() => setLogoutOpen(false)}
        footer={
          <>
            <Button type="button" variant="secondary" onClick={() => setLogoutOpen(false)}>
              Cancel
            </Button>
            <Button
              type="button"
              variant="primary"
              loading={loggingOut}
              disabled={loggingOut}
              onClick={confirmLogout}
            >
              Sign out
            </Button>
          </>
        }
      >
        <p>
          This discards your access token on this device. Your MongoDB account and study data
          remain on the server. Sign in again to continue.
        </p>
      </Modal>
    </div>
  );
}

export default AppShell;
