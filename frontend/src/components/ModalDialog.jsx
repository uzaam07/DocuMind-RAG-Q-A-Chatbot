import { useEffect, useRef } from 'react';

/**
 * Native <dialog> driven by an `open` prop. Used for the evidence bottom sheet
 * and the navigation drawer. Backdrop click and Esc both close it.
 */
export default function ModalDialog({ open, onClose, label, variant, children }) {
  const ref = useRef(null);

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);

  return (
    <dialog
      ref={ref}
      className={`modal modal--${variant}`}
      aria-label={label}
      onClose={onClose}
      onClick={(event) => {
        if (event.target === ref.current) onClose();
      }}
    >
      {open ? children : null}
    </dialog>
  );
}
