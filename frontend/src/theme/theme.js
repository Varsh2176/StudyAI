/** Theme mode persistence and DOM application (no React). */

export const THEME_STORAGE_KEY = "studyai_theme_mode";
export const THEME_MODES = ["light", "dark", "system"];
/** Default selected mode when nothing valid is stored. */
export const DEFAULT_THEME_MODE = "light";

export function isValidThemeMode(value) {
  return THEME_MODES.includes(value);
}

/**
 * Resolve OS preference to light|dark.
 * Only returns dark when the media query explicitly matches;
 * missing API / errors / no-preference → light.
 */
export function getSystemResolvedTheme() {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
    return "light";
  }
  try {
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    return mq && mq.matches === true ? "dark" : "light";
  } catch {
    return "light";
  }
}

export function readStoredThemeMode() {
  try {
    const raw = localStorage.getItem(THEME_STORAGE_KEY);
    if (isValidThemeMode(raw)) return raw;
  } catch {
    /* private mode / blocked storage */
  }
  return DEFAULT_THEME_MODE;
}

export function writeStoredThemeMode(mode) {
  if (!isValidThemeMode(mode)) return;
  try {
    localStorage.setItem(THEME_STORAGE_KEY, mode);
  } catch {
    /* ignore */
  }
}

/**
 * mode = saved selection (light|dark|system)
 * returns resolved appearance (light|dark) — never "system"
 */
export function resolveTheme(mode) {
  const safe = isValidThemeMode(mode) ? mode : DEFAULT_THEME_MODE;
  if (safe === "system") return getSystemResolvedTheme();
  return safe === "dark" ? "dark" : "light";
}

/** Apply resolved light|dark to <html> for CSS [data-theme]. */
export function applyResolvedTheme(resolved) {
  const theme = resolved === "dark" ? "dark" : "light";
  const root = document.documentElement;
  root.setAttribute("data-theme", theme);
  root.style.colorScheme = theme;
}
