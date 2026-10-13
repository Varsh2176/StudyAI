import { Link } from "react-router-dom";
import {
  Badge,
  Card,
  IconDocuments,
  IconExam,
  IconFlashcards,
  IconMindMap,
  IconProgress,
  IconQuiz,
  IconSummary,
} from "../components/ui";

/**
 * AI Learning Hub — discovery surface.
 * Local tools use uploaded document text via POST /ai/hub/local (no Gemini required).
 * Gemini remains an optional enhancement for topic-only generation.
 * Ask Your Notes uses Documents RAG (retrieval-only without Gemini).
 */

const GROUPS = [
  {
    id: "learn",
    title: "Learn",
    description: "Understand topics with assistance grounded in StudyWise workflows.",
    tools: [
      {
        id: "ask-notes",
        title: "Ask Your Notes",
        description:
          "Ask grounded questions about your uploaded PDFs with page citations (local TF-IDF/RAG; Gemini optional for synthesis).",
        status: "local",
        statusLabel: "Local",
        Icon: IconDocuments,
        actionTo: "/documents#ask-notes",
        actionLabel: "Open Documents",
        secondaryTo: "/documents",
        secondaryLabel: "Upload PDFs",
      },
      {
        id: "summary",
        title: "Summary Notes",
        description:
          "Extractive bullet summaries from your documents (local). Indexed-notes RAG and Gemini topic mode are optional enhancements.",
        status: "local",
        statusLabel: "Local",
        Icon: IconSummary,
        actionTo: "/hub/summary",
        actionLabel: "Open Summary Notes",
        secondaryTo: "/documents",
        secondaryLabel: "Upload PDFs",
      },
    ],
  },
  {
    id: "revise",
    title: "Revise",
    description: "Active recall and outlines from your notes; Gemini optional.",
    tools: [
      {
        id: "flashcards",
        title: "Flashcards",
        description:
          "Extractive flashcards from definitions and sentences in your PDFs. Gemini is optional for topic-only decks.",
        status: "local",
        statusLabel: "Local",
        Icon: IconFlashcards,
        actionTo: "/hub/flashcards",
        actionLabel: "Open Flashcards",
      },
      {
        id: "mindmaps",
        title: "Mind Maps",
        description:
          "Rule-based outline from document headings/sentences — not semantic AI. Gemini optional for topic-only maps.",
        status: "local",
        statusLabel: "Local",
        Icon: IconMindMap,
        actionTo: "/hub/mindmap",
        actionLabel: "Open Mind Maps",
      },
    ],
  },
  {
    id: "practice",
    title: "Practice",
    description: "Drills and short exams grounded in your uploaded text.",
    tools: [
      {
        id: "practice-questions",
        title: "Practice Questions",
        description:
          "Fill-in-the-blank drills from your document sentences. Gemini optional for topic-only sets.",
        status: "local",
        statusLabel: "Local",
        Icon: IconQuiz,
        actionTo: "/hub/practice",
        actionLabel: "Open Practice Questions",
      },
      {
        id: "mock-exams",
        title: "Mock Exams",
        description:
          "Multiple-choice items using terms found in your notes as answers/distractors. Gemini optional.",
        status: "local",
        statusLabel: "Local",
        Icon: IconExam,
        actionTo: "/hub/mock-exam",
        actionLabel: "Open Mock Exams",
      },
    ],
  },
  {
    id: "track",
    title: "Track",
    description: "Review real logged sessions and performance data for your student email.",
    tools: [
      {
        id: "progress",
        title: "Progress",
        description:
          "Load planned versus actual study time, subject completion rates, and recent sessions from the performance API.",
        status: "local",
        statusLabel: "Local",
        Icon: IconProgress,
        actionTo: "/progress",
        actionLabel: "Open Progress Tracking",
      },
    ],
  },
];

function statusBadgeVariant(status) {
  if (status === "local" || status === "available") return "success";
  if (status === "gemini" || status === "partial") return "info";
  if (status === "planned") return "warning";
  return "danger";
}

function LearningHub() {
  const studentEmail = localStorage.getItem("student_email") || "";

  return (
    <div className="sw-hub page-container">
      <div className="sw-hub-hero">
        <section className="sw-hub-intro" aria-labelledby="hub-heading">
          <p className="sw-hub-eyebrow">Unified workspace</p>
          <h2 id="hub-heading">AI Learning Hub</h2>
          <p>
            Hub tools work from your uploaded documents without a Gemini key. Gemini remains an
            optional enhancement for topic-only generation when configured. Tools never invent
            content client-side.
          </p>
        </section>
        <div className="sw-hub-hero-aside">
          {studentEmail ? (
            <div className="sw-hub-identity">
              <span className="sw-hub-identity-label">Student</span>
              <span className="sw-hub-identity-value">{studentEmail}</span>
            </div>
          ) : (
            <div className="sw-hub-identity sw-hub-identity--empty">
              <span className="sw-hub-identity-label">No student loaded</span>
              <Link to="/dashboard" className="sw-hub-identity-link">
                Load email on Dashboard
              </Link>
            </div>
          )}
          <Link to="/documents" className="sw-btn sw-btn--secondary sw-btn--sm">
            <IconDocuments size={16} /> Materials
          </Link>
        </div>
      </div>

      <div className="sw-hub-legend" role="note">
        <Badge variant="success">Local</Badge>
        <span>works from your uploaded notes without GEMINI_API_KEY</span>
        <Badge variant="info">Gemini-enhanced</Badge>
        <span>optional when a key is configured</span>
      </div>

      {GROUPS.map((group) => (
        <section
          key={group.id}
          className="sw-hub-group"
          aria-labelledby={`hub-group-${group.id}`}
        >
          <header className="sw-hub-group-head">
            <h3 id={`hub-group-${group.id}`}>{group.title}</h3>
            <p>{group.description}</p>
          </header>

          <div className="sw-hub-grid">
            {group.tools.map((tool) => {
              const Icon = tool.Icon;
              return (
                <Card key={tool.id} className={`sw-hub-card sw-hub-card--${tool.status}`}>
                  <div className="sw-hub-card-top">
                    <span className="sw-hub-card-icon" aria-hidden="true">
                      <Icon size={22} />
                    </span>
                    <Badge variant={statusBadgeVariant(tool.status)}>{tool.statusLabel}</Badge>
                  </div>
                  <h4 className="sw-hub-card-title">{tool.title}</h4>
                  <p className="sw-hub-card-desc">{tool.description}</p>
                  <div className="sw-hub-card-actions">
                    <Link to={tool.actionTo} className="sw-btn sw-btn--primary sw-btn--sm">
                      {tool.actionLabel}
                    </Link>
                    {tool.secondaryTo ? (
                      <Link to={tool.secondaryTo} className="sw-btn sw-btn--ghost sw-btn--sm">
                        {tool.secondaryLabel}
                      </Link>
                    ) : null}
                  </div>
                </Card>
              );
            })}
          </div>
        </section>
      ))}
    </div>
  );
}

export default LearningHub;
