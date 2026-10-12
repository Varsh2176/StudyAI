const COLOR_TOKENS = {
  primary: "var(--sw-primary)",
  success: "var(--sw-success)",
  warning: "var(--sw-warning)",
  danger: "var(--sw-danger)",
  info: "var(--sw-info)",
};

function ProgressBar({
  value = 0,
  min = 0,
  max = 100,
  label,
  color = "primary",
  className = "",
}) {
  const safeMax = max <= min ? min + 1 : max;
  const clamped = Math.min(safeMax, Math.max(min, Number(value) || 0));
  const percent = ((clamped - min) / (safeMax - min)) * 100;
  const fill = COLOR_TOKENS[color] || COLOR_TOKENS.primary;
  const displayLabel = label != null ? label : `${Math.round(percent)}%`;

  return (
    <div className={`sw-progress ${className}`.trim()}>
      <div className="sw-progress-meta">
        <span className="sw-progress-label">{displayLabel}</span>
        <span className="sw-progress-value">{Math.round(percent)}%</span>
      </div>
      <div
        className="sw-progress-track"
        role="progressbar"
        aria-valuenow={clamped}
        aria-valuemin={min}
        aria-valuemax={safeMax}
        aria-label={typeof displayLabel === "string" ? displayLabel : "Progress"}
      >
        <div
          className="sw-progress-fill"
          style={{ width: `${percent}%`, backgroundColor: fill }}
        />
      </div>
    </div>
  );
}

export default ProgressBar;
