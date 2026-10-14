import { useId } from "react";
import { useTheme } from "./ThemeContext";

/**
 * Accessible Light / Dark / System control.
 * Persists via ThemeProvider (studyai_theme_mode) — not student identity.
 */
function ThemeSelector({ className = "", size = "sm" }) {
  const { mode, setMode } = useTheme();
  const labelId = useId();
  const selectId = useId();

  return (
    <div className={`sw-theme-selector ${className}`.trim()}>
      <label id={labelId} htmlFor={selectId} className="sw-theme-selector-label">
        Theme
      </label>
      <select
        id={selectId}
        className={`sw-theme-selector-control sw-theme-selector-control--${size}`}
        aria-labelledby={labelId}
        value={mode}
        onChange={(e) => setMode(e.target.value)}
      >
        <option value="light">Light</option>
        <option value="dark">Dark</option>
        <option value="system">System</option>
      </select>
    </div>
  );
}

export default ThemeSelector;
