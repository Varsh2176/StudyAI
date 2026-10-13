import { useEffect } from "react";
import { Link, useLocation } from "react-router-dom";
import PdfDocumentsPanel from "../components/PdfDocumentsPanel";

function Documents() {
  const location = useLocation();

  useEffect(() => {
    if (location.hash !== "#ask-notes") return undefined;
    const timer = window.setTimeout(() => {
      const target = document.getElementById("ask-notes");
      if (target) {
        target.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    }, 0);
    return () => window.clearTimeout(timer);
  }, [location.hash, location.key]);

  return (
    <div className="sw-docs-page page-container">
      <div className="sw-docs-hero">
        <section className="sw-docs-intro" aria-labelledby="docs-heading">
          <p className="sw-docs-eyebrow">Study materials</p>
          <h2 id="docs-heading">Documents</h2>
          <p>
            Upload PDF notes for extraction and local TF-IDF indexing, then ask
            grounded questions with page citations from your own materials.
          </p>
        </section>
        <div className="sw-docs-hero-actions">
          <a href="#ask-notes" className="sw-btn sw-btn--primary sw-btn--sm">
            Ask about notes
          </a>
          <Link to="/tutor" className="sw-btn sw-btn--secondary sw-btn--sm">
            Open AI Tutor
          </Link>
        </div>
      </div>

      <PdfDocumentsPanel />
    </div>
  );
}

export default Documents;
