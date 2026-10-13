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
  IconTutor,
} from "../components/ui";

/**
 * AI Learning Hub — discovery surface.
 * Tools that need Gemini use the existing /ai/tutor API.
 * Summary Notes can also use Documents RAG for indexed PDFs.
 */

const GROUPS = [
  {
    id: "learn",
    title: "Learn",
    description: "Understand topics with assistance grounded in StudyWise workflows.",
    tools: [
      {
        id: "tutor",
        title: "AI Tutor",
        description:
          "Ask academic questions and get student-friendly explanations from the configured tutor API.",
        status: "available",
        statusLabel: "Available",
        Icon: IconTutor,
        actionTo: "/tutor",
        actionLabel: "Open AI Tutor",
      },
      {
        id: "summary",
        title: "Summary Notes",
        description:
          "Generate concise study summaries from a topic (AI Tutor) or from your indexed PDFs (Documents RAG).",
        status: "available",
        statusLabel: "Available",
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
    description: "Active recall and concept organization powered by the AI Tutor.",
    tools: [
      {
        id: "flashcards",
        title: "Flashcards",
        description:
          "Generate flip cards for a topic. Cards appear only when the tutor returns parseable JSON.",
        status: "available",
        statusLabel: "Available",
        Icon: IconFlashcards,
        actionTo: "/hub/flashcards",
        actionLabel: "Open Flashcards",
      },
      {
        id: "mindmaps",
        title: "Mind Maps",
        description:
          "Build a hierarchical concept outline from the tutor and view it as a mind-map style tree.",
        status: "available",
        statusLabel: "Available",
        Icon: IconMindMap,
        actionTo: "/hub/mindmap",
        actionLabel: "Open Mind Maps",
      },
    ],
  },
  {
    id: "practice",
    title: "Practice",
    description: "Topic drills and short mock assessments generated through the tutor API.",
    tools: [
      {
        id: "practice-questions",
        title: "Practice Questions",
        description:
          "Generate topic questions with revealable answers. Requires a configured Gemini key.",
        status: "available",
        statusLabel: "Available",
        Icon: IconQuiz,
        actionTo: "/hub/practice",
        actionLabel: "Open Practice Questions",
      },
      {
        id: "mock-exams",
        title: "Mock Exams",
        description:
          "Generate a short multiple-choice set, attempt it, and score against the model answer key.",
        status: "available",
        statusLabel: "Available",
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
        status: "available",
        statusLabel: "Available",
        Icon: IconProgress,
        actionTo: "/progress",
        actionLabel: "Open Progress Tracking",
      },
    ],
  },
];

function statusBadgeVariant(status) {
  if (status === "available") return "success";
  if (status === "partial") return "info";
  return "warning";
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
            Open each tool below to generate real study content through the existing AI Tutor or
            Documents RAG APIs. If Gemini is not configured, tools show that status instead of fake
            output.
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
        <Badge variant="success">Available</Badge>
        <span>opens a working tool page</span>
        <Badge variant="info">Needs API key</Badge>
        <span>tutor-backed tools require GEMINI_API_KEY</span>
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
