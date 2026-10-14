/**
 * Inline SVG icons for StudyWise UI. Decorative by default (aria-hidden).
 */

function SvgIcon({ children, size = 20, className = "", title, ...rest }) {
  const ariaHidden = title ? undefined : true;
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={`sw-icon ${className}`.trim()}
      aria-hidden={ariaHidden}
      role={title ? "img" : undefined}
      {...rest}
    >
      {title ? <title>{title}</title> : null}
      {children}
    </svg>
  );
}

export function IconDashboard(props) {
  return (
    <SvgIcon {...props}>
      <rect x="3" y="3" width="7" height="9" rx="1" />
      <rect x="14" y="3" width="7" height="5" rx="1" />
      <rect x="14" y="12" width="7" height="9" rx="1" />
      <rect x="3" y="16" width="7" height="5" rx="1" />
    </SvgIcon>
  );
}

export function IconPredict(props) {
  return (
    <SvgIcon {...props}>
      <path d="M4 19V5" />
      <path d="M4 19h16" />
      <path d="M8 15l3-4 3 2 4-6" />
    </SvgIcon>
  );
}

export function IconChart(props) {
  return <IconPredict {...props} />;
}

export function IconPlanner(props) {
  return (
    <SvgIcon {...props}>
      <rect x="3" y="5" width="18" height="16" rx="2" />
      <path d="M3 10h18" />
      <path d="M8 3v4" />
      <path d="M16 3v4" />
      <path d="M8 14h.01" />
      <path d="M12 14h.01" />
      <path d="M16 14h.01" />
    </SvgIcon>
  );
}

export function IconCalendar(props) {
  return <IconPlanner {...props} />;
}

export function IconTutor(props) {
  return (
    <SvgIcon {...props}>
      <path d="M21 12a8 8 0 0 1-8 8H7l-4 3V12a8 8 0 1 1 18 0z" />
    </SvgIcon>
  );
}

export function IconChat(props) {
  return <IconTutor {...props} />;
}

export function IconDocuments(props) {
  return (
    <SvgIcon {...props}>
      <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" />
      <path d="M14 3v5h5" />
      <path d="M9 13h6" />
      <path d="M9 17h4" />
    </SvgIcon>
  );
}

export function IconFile(props) {
  return <IconDocuments {...props} />;
}

export function IconProgress(props) {
  return (
    <SvgIcon {...props}>
      <path d="M12 3a9 9 0 1 0 9 9" />
      <path d="M12 7v5l3 2" />
    </SvgIcon>
  );
}

export function IconProfile(props) {
  return (
    <SvgIcon {...props}>
      <circle cx="12" cy="8" r="4" />
      <path d="M4 21c1.5-4 5-6 8-6s6.5 2 8 6" />
    </SvgIcon>
  );
}

export function IconSend(props) {
  return (
    <SvgIcon {...props}>
      <path d="M22 2L11 13" />
      <path d="M22 2l-7 20-4-9-9-4 20-7z" />
    </SvgIcon>
  );
}

export function IconUpload(props) {
  return (
    <SvgIcon {...props}>
      <path d="M12 16V5" />
      <path d="M7 10l5-5 5 5" />
      <path d="M4 19h16" />
    </SvgIcon>
  );
}

export function IconCheck(props) {
  return (
    <SvgIcon {...props}>
      <path d="M20 6L9 17l-5-5" />
    </SvgIcon>
  );
}

export function IconAlert(props) {
  return (
    <SvgIcon {...props}>
      <path d="M10.3 4.3L2.6 18a2 2 0 0 0 1.7 3h15.4a2 2 0 0 0 1.7-3L13.7 4.3a2 2 0 0 0-3.4 0z" />
      <path d="M12 9v4" />
      <path d="M12 17h.01" />
    </SvgIcon>
  );
}

export function IconClock(props) {
  return (
    <SvgIcon {...props}>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5l3 2" />
    </SvgIcon>
  );
}

export function IconBook(props) {
  return (
    <SvgIcon {...props}>
      <path d="M4 5a2 2 0 0 1 2-2h12v18H6a2 2 0 0 1-2-2V5z" />
      <path d="M8 7h6" />
      <path d="M8 11h8" />
    </SvgIcon>
  );
}

export function IconSparkles(props) {
  return (
    <SvgIcon {...props}>
      <path d="M12 3l1.5 4.5L18 9l-4.5 1.5L12 15l-1.5-4.5L6 9l4.5-1.5L12 3z" />
      <path d="M19 14l.8 2.2L22 17l-2.2.8L19 20l-.8-2.2L16 17l2.2-.8L19 14z" />
    </SvgIcon>
  );
}

export function IconMenu(props) {
  return (
    <SvgIcon {...props}>
      <path d="M4 7h16" />
      <path d="M4 12h16" />
      <path d="M4 17h16" />
    </SvgIcon>
  );
}

export function IconClose(props) {
  return (
    <SvgIcon {...props}>
      <path d="M6 6l12 12" />
      <path d="M18 6L6 18" />
    </SvgIcon>
  );
}

export function IconRefresh(props) {
  return (
    <SvgIcon {...props}>
      <path d="M21 12a9 9 0 1 1-2.6-6.1" />
      <path d="M21 4v6h-6" />
    </SvgIcon>
  );
}

export function IconHub(props) {
  return (
    <SvgIcon {...props}>
      <circle cx="12" cy="12" r="3" />
      <path d="M12 3v3" />
      <path d="M12 18v3" />
      <path d="M3 12h3" />
      <path d="M18 12h3" />
      <path d="M5.6 5.6l2.1 2.1" />
      <path d="M16.3 16.3l2.1 2.1" />
      <path d="M18.4 5.6l-2.1 2.1" />
      <path d="M7.7 16.3l-2.1 2.1" />
    </SvgIcon>
  );
}

export function IconFlashcards(props) {
  return (
    <SvgIcon {...props}>
      <rect x="5" y="4" width="12" height="16" rx="2" />
      <path d="M9 4v16" />
      <path d="M17 8h2a1 1 0 0 1 1 1v11a2 2 0 0 1-2 2h-9" />
    </SvgIcon>
  );
}

export function IconMindMap(props) {
  return (
    <SvgIcon {...props}>
      <circle cx="12" cy="12" r="2.5" />
      <circle cx="5" cy="6" r="2" />
      <circle cx="19" cy="6" r="2" />
      <circle cx="5" cy="18" r="2" />
      <circle cx="19" cy="18" r="2" />
      <path d="M10.2 10.2L6.5 7.5" />
      <path d="M13.8 10.2L17.5 7.5" />
      <path d="M10.2 13.8L6.5 16.5" />
      <path d="M13.8 13.8L17.5 16.5" />
    </SvgIcon>
  );
}

export function IconQuiz(props) {
  return (
    <SvgIcon {...props}>
      <path d="M9 9a3 3 0 1 1 4.2 2.7c-.7.3-1.2.9-1.2 1.6V14" />
      <path d="M12 17h.01" />
      <circle cx="12" cy="12" r="9" />
    </SvgIcon>
  );
}

export function IconExam(props) {
  return (
    <SvgIcon {...props}>
      <path d="M8 4h8a2 2 0 0 1 2 2v14l-3-2-3 2-3-2-3 2V6a2 2 0 0 1 2-2z" />
      <path d="M9 9h6" />
      <path d="M9 13h6" />
    </SvgIcon>
  );
}

export function IconSummary(props) {
  return (
    <SvgIcon {...props}>
      <path d="M6 4h9l3 3v13a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1z" />
      <path d="M14 4v4h4" />
      <path d="M8 12h8" />
      <path d="M8 16h6" />
    </SvgIcon>
  );
}

const Icons = {
  dashboard: IconDashboard,
  predict: IconPredict,
  chart: IconChart,
  planner: IconPlanner,
  calendar: IconCalendar,
  tutor: IconTutor,
  chat: IconChat,
  documents: IconDocuments,
  file: IconFile,
  progress: IconProgress,
  profile: IconProfile,
  send: IconSend,
  upload: IconUpload,
  check: IconCheck,
  alert: IconAlert,
  clock: IconClock,
  book: IconBook,
  sparkles: IconSparkles,
  menu: IconMenu,
  close: IconClose,
  refresh: IconRefresh,
  hub: IconHub,
  flashcards: IconFlashcards,
  mindmap: IconMindMap,
  quiz: IconQuiz,
  exam: IconExam,
  summary: IconSummary,
};

export default Icons;
