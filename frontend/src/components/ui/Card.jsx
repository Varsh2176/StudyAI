function Card({
  children,
  title,
  action,
  footer,
  interactive = false,
  className = "",
  ...rest
}) {
  const classes = [
    "sw-card",
    interactive ? "sw-card--interactive" : "",
    className,
  ]
    .filter(Boolean)
    .join(" ");

  const hasHeader = title != null || action != null;

  return (
    <div className={classes} {...rest}>
      {hasHeader ? (
        <div className="sw-card-header">
          {title != null ? <h2 className="sw-card-title">{title}</h2> : <span />}
          {action != null ? <div className="sw-card-action">{action}</div> : null}
        </div>
      ) : null}
      <div className="sw-card-body">{children}</div>
      {footer != null ? <div className="sw-card-footer">{footer}</div> : null}
    </div>
  );
}

export default Card;
