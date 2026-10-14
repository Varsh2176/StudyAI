import { Link, Outlet } from "react-router-dom";
import { ThemeSelector } from "../theme";
import { IconChart, IconPlanner, IconTutor } from "./ui/Icons";

/**
 * Layout for auth screens (Register at "/").
 * Split-screen brand panel + form panel; theme control stays here only.
 */
function AuthLayout() {
  return (
    <div className="app-container auth-app">
      <div className="auth-split">
        <aside className="auth-brand" aria-label="StudyWise AI">
          <div className="auth-brand-glow" aria-hidden="true" />
          <div className="auth-brand-inner">
            <Link to="/" className="auth-brand-logo">
              StudyWise AI
            </Link>

            <div className="auth-brand-copy">
              <h1 className="auth-brand-headline">Learn Smarter. Achieve Higher.</h1>
              <p className="auth-brand-support">
                Personalized study planning and AI-powered learning that adapt to
                your goals, schedule, and progress.
              </p>
            </div>

            <div className="auth-brand-visual" aria-hidden="true">
              <div className="auth-viz-orbit auth-viz-orbit--a" />
              <div className="auth-viz-orbit auth-viz-orbit--b" />
              <div className="auth-viz-core">
                <span className="auth-viz-book" />
                <span className="auth-viz-node auth-viz-node--1" />
                <span className="auth-viz-node auth-viz-node--2" />
                <span className="auth-viz-node auth-viz-node--3" />
              </div>
            </div>

            <ul className="auth-brand-benefits">
              <li>
                <span className="auth-benefit-icon">
                  <IconPlanner size={18} />
                </span>
                <span>Personalized study plans</span>
              </li>
              <li>
                <span className="auth-benefit-icon">
                  <IconChart size={18} />
                </span>
                <span>Performance insights</span>
              </li>
              <li>
                <span className="auth-benefit-icon">
                  <IconTutor size={18} />
                </span>
                <span>AI-assisted learning</span>
              </li>
            </ul>
          </div>
        </aside>

        <section className="auth-form-panel">
          <header className="auth-form-toolbar">
            <span className="auth-form-toolbar-brand" aria-hidden="true">
              StudyWise AI
            </span>
            <ThemeSelector size="sm" />
          </header>
          <main className="auth-form-main" id="main-content">
            <Outlet />
          </main>
        </section>
      </div>
    </div>
  );
}

export default AuthLayout;
