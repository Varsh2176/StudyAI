import { useId } from "react";

function Select({
  label,
  hint,
  error,
  id,
  children,
  className = "",
  disabled = false,
  ...rest
}) {
  const autoId = useId();
  const fieldId = id || autoId;
  const hintId = `${fieldId}-hint`;
  const errorId = `${fieldId}-error`;
  const describedBy = [
    hint ? hintId : null,
    error ? errorId : null,
  ]
    .filter(Boolean)
    .join(" ") || undefined;

  return (
    <div className={`sw-field ${error ? "sw-field--error" : ""} ${className}`.trim()}>
      {label != null ? (
        <label className="sw-field-label" htmlFor={fieldId}>
          {label}
        </label>
      ) : null}
      <select
        id={fieldId}
        className="sw-field-control sw-field-control--select"
        disabled={disabled}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy}
        {...rest}
      >
        {children}
      </select>
      {hint && !error ? (
        <p id={hintId} className="sw-field-hint">
          {hint}
        </p>
      ) : null}
      {error ? (
        <p id={errorId} className="sw-field-error" role="alert">
          {error}
        </p>
      ) : null}
    </div>
  );
}

export default Select;
