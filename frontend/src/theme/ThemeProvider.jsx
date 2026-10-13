import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  useSyncExternalStore,
} from "react";
import {
  DEFAULT_THEME_MODE,
  THEME_MODES,
  applyResolvedTheme,
  getSystemResolvedTheme,
  isValidThemeMode,
  readStoredThemeMode,
  resolveTheme,
  writeStoredThemeMode,
} from "./theme";
import { ThemeContext } from "./ThemeContext";

function subscribeSystemPreference(onStoreChange) {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
    return () => {};
  }
  let mq;
  try {
    mq = window.matchMedia("(prefers-color-scheme: dark)");
  } catch {
    return () => {};
  }
  const handler = () => onStoreChange();
  if (typeof mq.addEventListener === "function") {
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }
  if (typeof mq.addListener === "function") {
    mq.addListener(handler);
    return () => mq.removeListener(handler);
  }
  return () => {};
}

function getSystemSnapshot() {
  return getSystemResolvedTheme();
}

function getServerSnapshot() {
  return "light";
}

export function ThemeProvider({ children }) {
  const [mode, setModeState] = useState(() => readStoredThemeMode());

  // Tracks OS preference; only used when mode === "system".
  const systemResolved = useSyncExternalStore(
    subscribeSystemPreference,
    getSystemSnapshot,
    getServerSnapshot
  );

  // Selected mode vs resolved appearance must stay distinct.
  const resolved =
    mode === "system" ? systemResolved : mode === "dark" ? "dark" : "light";

  useEffect(() => {
    applyResolvedTheme(resolved);
  }, [resolved]);

  const setMode = useCallback((next) => {
    const safe = isValidThemeMode(next) ? next : DEFAULT_THEME_MODE;
    setModeState(safe);
    writeStoredThemeMode(safe);
    applyResolvedTheme(resolveTheme(safe));
  }, []);

  const value = useMemo(
    () => ({
      mode,
      resolved,
      setMode,
      modes: THEME_MODES,
    }),
    [mode, resolved, setMode]
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export default ThemeProvider;
