import { IconRefresh } from "./Icons";

const VARIANT_CLASS = {
  primary: "sw-btn--primary",
  secondary: "sw-btn--secondary",
  ghost: "sw-btn--ghost",
  danger: "sw-btn--danger",
};

const SIZE_CLASS = {
  sm: "sw-btn--sm",
  md: "sw-btn--md",
};

function Button({
  children,
  variant = "primary",
  size = "md",
  loading = false,
  disabled = false,
  type = "button",
  className = "",
  ref,
  ...rest
}) {
  const isDisabled = disabled || loading;
  const classes = [
    "sw-btn",
    VARIANT_CLASS[variant] || VARIANT_CLASS.primary,
    SIZE_CLASS[size] || SIZE_CLASS.md,
    loading ? "sw-btn--loading" : "",
    className,
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <button
      ref={ref}
      type={type}
      className={classes}
      disabled={isDisabled}
      aria-busy={loading || undefined}
      {...rest}
    >
      {loading ? (
        <span className="sw-btn-spinner" aria-hidden="true">
          <IconRefresh size={size === "sm" ? 14 : 16} className="sw-btn-spinner-icon" />
        </span>
      ) : null}
      <span className={loading ? "sw-btn-label sw-btn-label--busy" : "sw-btn-label"}>
        {children}
      </span>
    </button>
  );
}

export default Button;
