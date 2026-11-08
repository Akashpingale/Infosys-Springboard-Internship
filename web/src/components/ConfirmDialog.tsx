/**
 * Confirm dialog (KIRO_UI_UPGRADE_SPEC.md Sections 6.5 and 6.9).
 *
 * Deleting a saved validation cannot be undone, so it is asked for once, in words that say what
 * will go. The cancel button is the one that carries focus when the dialog opens, so pressing
 * Enter by habit does not delete anything.
 *
 * Like the source drawer, it is a native <dialog> opened with showModal(), which supplies the focus
 * trap, Escape and the return of focus to whatever opened it.
 */

import * as React from 'react';

import { Button } from '@/components/ui/button';

export interface ConfirmDialogProps {
  open: boolean;
  title: string;
  /** What will happen, in one or two sentences. */
  children: React.ReactNode;
  confirmLabel: string;
  onConfirm: () => void;
  onCancel: () => void;
  /** Shows a spinner on the confirm button while the request is in flight. */
  busy?: boolean;
}

export function ConfirmDialog({ open, title, children, confirmLabel, onConfirm, onCancel, busy }: ConfirmDialogProps) {
  const ref = React.useRef<HTMLDialogElement>(null);
  const cancelRef = React.useRef<HTMLButtonElement>(null);
  const headingId = React.useId();

  React.useEffect(() => {
    const dialog = ref.current;
    if (!dialog) {
      return;
    }
    if (open && !dialog.open) {
      if (typeof dialog.showModal === 'function') {
        dialog.showModal();
      } else {
        dialog.setAttribute('open', '');
      }
      cancelRef.current?.focus();
    }
    if (!open && dialog.open) {
      dialog.close();
    }
  }, [open]);

  // The fallback above is not modal, so Escape is handled here as well as by the browser.
  React.useEffect(() => {
    if (!open) {
      return;
    }
    function onKeyDown(event: KeyboardEvent): void {
      if (event.key === 'Escape') {
        event.preventDefault();
        onCancel();
      }
    }
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [open, onCancel]);

  if (!open) {
    return null;
  }

  return (
    <dialog
      ref={ref}
      aria-labelledby={headingId}
      onCancel={(event) => {
        event.preventDefault();
        onCancel();
      }}
      onClick={(event) => {
        if (event.target === ref.current) {
          onCancel();
        }
      }}
      className="m-auto max-w-form bg-transparent p-4 backdrop:bg-black/60"
    >
      <div className="space-y-4 rounded-panel border border-line bg-surface p-6 shadow-overlay">
        <h2 id={headingId}>{title}</h2>
        <div className="max-w-prose text-body text-content-secondary">{children}</div>
        <div className="flex flex-col gap-3 sm:flex-row-reverse sm:justify-start">
          <Button variant="danger" onClick={onConfirm} loading={busy}>
            {confirmLabel}
          </Button>
          <Button ref={cancelRef} variant="secondary" onClick={onCancel} disabled={busy}>
            Keep it
          </Button>
        </div>
      </div>
    </dialog>
  );
}
