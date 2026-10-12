import { IconSparkles } from "./Icons";

function EmptyState({
  icon,
  title,
  description,
  action,
  className = "",
}) {
  return (
    <div className={`sw-empty ${className}`.trim()}>
      <div className="sw-empty-icon" aria-hidden="true">
        {icon || <IconSparkles size={28} />}
      </div>
      {title ? <h3 className="sw-empty-title">{title}</h3> : null}
      {description ? <p className="sw-empty-desc">{description}</p> : null}
      {action ? <div className="sw-empty-action">{action}</div> : null}
    </div>
  );
}

export default EmptyState;
