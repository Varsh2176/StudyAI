/**
 * Deterministic subject → StudyWise color token mapping.
 * Same trimmed, lowercased name always maps to the same --sw-subject-N pair.
 */

const SUBJECT_TOKENS = [
  { solid: "var(--sw-subject-1)", soft: "var(--sw-subject-1-soft)" },
  { solid: "var(--sw-subject-2)", soft: "var(--sw-subject-2-soft)" },
  { solid: "var(--sw-subject-3)", soft: "var(--sw-subject-3-soft)" },
  { solid: "var(--sw-subject-4)", soft: "var(--sw-subject-4-soft)" },
  { solid: "var(--sw-subject-5)", soft: "var(--sw-subject-5-soft)" },
  { solid: "var(--sw-subject-6)", soft: "var(--sw-subject-6-soft)" },
  { solid: "var(--sw-subject-7)", soft: "var(--sw-subject-7-soft)" },
  { solid: "var(--sw-subject-8)", soft: "var(--sw-subject-8-soft)" },
];

function hashSubjectName(name) {
  const normalized = String(name || "")
    .trim()
    .toLowerCase();
  let hash = 0;
  for (let i = 0; i < normalized.length; i += 1) {
    hash = (hash * 31 + normalized.charCodeAt(i)) >>> 0;
  }
  return hash;
}

export function subjectColor(name) {
  const index = hashSubjectName(name) % SUBJECT_TOKENS.length;
  return SUBJECT_TOKENS[index];
}

export default subjectColor;
