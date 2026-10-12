import { useCallback, useEffect, useId, useRef, useState } from "react";
import { Link, Outlet, useLocation, useNavigate } from "react-router-dom";
import Navbar from "./Navbar";
import { Button, Modal } from "./ui";

const PAGE_TITLES = {
  "/dashboard": "Dashboard",
  "/predict": "Predict Score & Risk",
  "/planner": "Study Planner",
  "/tutor": "AI Tutor",
  "/documents": "Documents",
  "/progress": "Progress",
  "/profile": "Student Profile",
};

function titleForPath(pathname) {
  return PAGE_TITLES[pathname] || "StudyWise AI";
}

/**
 * App chrome: fixed sidebar (desktop), accessible mobile drawer, sticky header.
 * Page components render via <Outlet /> — pages themselves are not modified in Phase 1.
 *
 * Drawer open state is tied to location.key so route changes close it without
 * setState-inside-effect (satisfies react-hooks/set-state-in-effect).
 */
function AppShell() {
  const location = useLocation();
  const navigate = useNavigate();
  const [drawerKey, setDrawerKey] = useState(null);
  const [switchOpen, setSwitchOpen] = useState(false);
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

  // Lock body scroll while drawer is open
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

  // Esc closes; focus moves into drawer on open and back to toggle on close
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

  const confirmSwitchStudent = () => {
    // Clears only the app's existing local identity key — no backend call.
    localStorage.removeItem("student_email");
    setSwitchOpen(false);
    setDrawerKey(null);
    navigate("/");
  };

  const pageTitle = titleForPath(location.pathname);

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
        <Link to="/dashboard" className="sw-sidebar-brand" onClick={closeDrawer}>
          StudyWise AI
        </Link>
        <div className="sw-sidebar-nav">
          <Navbar variant="sidebar" navId={navId} onNavigate={closeDrawer} />
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
            <span className="sw-menu-toggle-icon" aria-hidden="true" />
          </button>
          <h1 className="sw-page-title">{pageTitle}</h1>
          <div className="sw-header-actions">
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={() => setSwitchOpen(true)}
            >
              Switch student
            </Button>
          </div>
        </header>

        <main className="sw-shell-content" id="main-content">
          <Outlet />
        </main>
      </div>

      <Modal
        open={switchOpen}
        title="Switch student?"
        onClose={() => setSwitchOpen(false)}
        footer={
          <>
            <Button type="button" variant="secondary" onClick={() => setSwitchOpen(false)}>
              Cancel
            </Button>
            <Button type="button" variant="primary" onClick={confirmSwitchStudent}>
              Switch student
            </Button>
          </>
        }
      >
        <p>
          This clears the locally stored student email on this device and returns you to
          registration so you can continue as a different student. It does not call the server
          or delete any account data.
        </p>
      </Modal>
    </div>
  );
}

export default AppShell;
