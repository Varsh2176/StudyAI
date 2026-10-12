import Button from "./Button";
import { IconAlert } from "./Icons";

function ErrorMessage({ message, onRetry, retryLabel = "Retry", className = "" }) {
  if (!message) return null;

  return (
    <div className={`sw-error ${className}`.trim()} role="alert">
      <div className="sw-error-main">
        <IconAlert className="sw-error-icon" size={20} />
        <p className="sw-error-text">{message}</p>
      </div>
      {typeof onRetry === "function" ? (
        <Button variant="secondary" size="sm" type="button" onClick={onRetry}>
          {retryLabel}
        </Button>
      ) : null}
    </div>
  );
}

export default ErrorMessage;
