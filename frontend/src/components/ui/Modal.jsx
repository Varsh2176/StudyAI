import { useEffect, useId, useRef } from "react";
import { IconClose } from "./Icons";
import Button from "./Button";

const FOCUSABLE =
  'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

function Modal({
  open,
  title,
  children,
  onClose,
  footer,
  className = "",
}) {
  const titleId = useId();
  const dialogRef = useRef(null);
  const previouslyFocused = useRef(null);

  useEffect(() => {
    if (!open) return undefined;

    previouslyFocused.current = document.activeElement;
    document.body.classList.add("sw-modal-lock");

    const dialog = dialogRef.current;
    const focusables = dialog ? dialog.querySelectorAll(FOCUSABLE) : [];
    if (focusables.length > 0) {
      focusables[0].focus();
    } else if (dialog) {
      dialog.focus();
    }

    const onKeyDown = (event) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose?.();
        return;
      }
      if (event.key !== "Tab" || !dialog) return;

      const nodes = Array.from(dialog.querySelectorAll(FOCUSABLE));
      if (nodes.length === 0) {
        event.preventDefault();
        return;
      }
      const first = nodes[0];
      const last = nodes[nodes.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };

    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.body.classList.remove("sw-modal-lock");
      const opener = previouslyFocused.current;
      if (opener && typeof opener.focus === "function") {
        opener.focus();
      }
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="sw-modal-root">
      <button
        type="button"
        className="sw-modal-backdrop"
        aria-label="Close dialog"
        onClick={() => onClose?.()}
      />
      <div
        ref={dialogRef}
        className={`sw-modal ${className}`.trim()}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
      >
        <div className="sw-modal-header">
          <h2 id={titleId} className="sw-modal-title">
            {title}
          </h2>
          <Button
            variant="ghost"
            size="sm"
            aria-label="Close"
            onClick={() => onClose?.()}
          >
            <IconClose size={18} />
          </Button>
        </div>
        <div className="sw-modal-body">{children}</div>
        {footer != null ? <div className="sw-modal-footer">{footer}</div> : null}
      </div>
    </div>
  );
}

export default Modal;
