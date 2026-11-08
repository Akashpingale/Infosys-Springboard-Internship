/**
 * Field (KIRO_UI_UPGRADE_SPEC.md Sections 6.4, 6.5 and 8.1).
 *
 * Label above, control, then one line below it. An error replaces the helper text in the same
 * place, so nothing moves when it appears. The control is tied to its label, its description and
 * its error through ids, and `aria-invalid` marks it, so a screen reader announces the problem.
 */

import * as React from 'react';

import { Label } from '@/components/ui/label';
import { cn } from '@/lib/cn';

export interface FieldProps {
  id: string;
  label: string;
  /** Marks the field required, both visually and for assistive technology. */
  required?: boolean;
  helper?: string;
  error?: string;
  /** Shows "123 / 2000" beside the helper line, where a limit exists. */
  counter?: { value: number; max: number };
  className?: string;
  children: (controlProps: {
    id: string;
    'aria-describedby': string | undefined;
    'aria-invalid': boolean | undefined;
    'aria-required': boolean | undefined;
  }) => React.ReactNode;
}

export function Field({ id, label, required, helper, error, counter, className, children }: FieldProps) {
  const helperId = `${id}-helper`;
  const errorId = `${id}-error`;
  const describedBy = error ? errorId : helper ? helperId : undefined;
  const overLimit = counter ? counter.value > counter.max : false;

  return (
    <div className={cn('space-y-2', className)}>
      <div className="flex items-baseline justify-between gap-4">
        <Label htmlFor={id}>
          {label}
          {required ? (
            <>
              <span aria-hidden="true" className="ml-1 text-content-muted">
                *
              </span>
              <span className="sr-only"> (required)</span>
            </>
          ) : null}
        </Label>
        {counter ? (
          <span
            className={cn('tabular text-micro', overLimit ? 'text-danger' : 'text-content-muted')}
            // The live count would interrupt typing, so it is not announced.
            aria-hidden="true"
          >
            {counter.value} / {counter.max}
          </span>
        ) : null}
      </div>

      {children({
        id,
        'aria-describedby': describedBy,
        'aria-invalid': error ? true : undefined,
        'aria-required': required ? true : undefined,
      })}

      {error ? (
        <p id={errorId} className="text-small text-danger">
          {error}
        </p>
      ) : helper ? (
        <p id={helperId} className="text-small text-content-muted">
          {helper}
        </p>
      ) : null}
    </div>
  );
}

const CONTROL = cn(
  'w-full rounded-control border border-line-strong bg-raised px-3 py-2',
  'text-body text-content placeholder:text-content-muted',
  'transition-colors duration-tab hover:border-primary',
  'aria-[invalid=true]:border-danger',
  'disabled:cursor-not-allowed disabled:opacity-50',
);

/** A single-line text input, styled once so every screen matches. */
export const TextInput = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  function TextInput({ className, ...props }, ref) {
    return <input ref={ref} type="text" className={cn(CONTROL, className)} {...props} />;
  },
);

/** A multi-line text area. It grows by rows, never by shifting the page. */
export const TextArea = React.forwardRef<HTMLTextAreaElement, React.TextareaHTMLAttributes<HTMLTextAreaElement>>(
  function TextArea({ className, rows = 5, ...props }, ref) {
    return <textarea ref={ref} rows={rows} className={cn(CONTROL, 'resize-y', className)} {...props} />;
  },
);

export { CONTROL as controlClassName };
