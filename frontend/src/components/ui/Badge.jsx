const VARIANT_CLASS = {
  neutral: "sw-badge--neutral",
  success: "sw-badge--success",
  warning: "sw-badge--warning",
  danger: "sw-badge--danger",
  info: "sw-badge--info",
  primary: "sw-badge--primary",
};

function Badge({ children, variant = "neutral", className = "", ...rest }) {
  const text = children == null || children === "" ? "—" : children;
  const classes = [
    "sw-badge",
    VARIANT_CLASS[variant] || VARIANT_CLASS.neutral,
    className,
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <span className={classes} {...rest}>
      {text}
    </span>
  );
}

export default Badge;
