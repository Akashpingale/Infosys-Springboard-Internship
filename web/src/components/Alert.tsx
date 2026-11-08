/**
 * Alert (KIRO_UI_UPGRADE_SPEC.md Sections 6.2, 6.5 and 6.9).
 *
 * A message with an icon and a word, never colour alone. An error carries role="alert" so a screen
 * reader announces it as soon as it appears, which is what a failed submission needs.
 */

import { AlertTriangle, CheckCircle2, Info, XCircle } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';

import { cn } from '@/lib/cn';

export type AlertTone = 'info' | 'success' | 'warning' | 'error';

const TONE: Record<AlertTone, { Icon: LucideIcon; className: string; word: string }> = {
  info: { Icon: Info, className: 'border-info-border bg-info-bg', word: 'Note' },
  success: { Icon: CheckCircle2, className: 'border-success-border bg-success-bg', word: 'Done' },
  warning: { Icon: AlertTriangle, className: 'border-warning-border bg-warning-bg', word: 'Warning' },
  error: { Icon: XCircle, className: 'border-danger-border bg-danger-bg', word: 'Error' },
};

const ICON_COLOUR: Record<AlertTone, string> = {
  info: 'text-info',
  success: 'text-success',
  warning: 'text-warning',
  error: 'text-danger',
};

export interface AlertProps {
  tone: AlertTone;
  children: React.ReactNode;
  /** Shown above the message, for example "Can't start the validation". */
  title?: string;
  action?: React.ReactNode;
  className?: string;
}

export function Alert({ tone, children, title, action, className }: AlertProps) {
  const { Icon, className: toneClass, word } = TONE[tone];
  return (
    <div
      role={tone === 'error' ? 'alert' : 'status'}
      className={cn('flex items-start gap-3 rounded-panel border p-4', toneClass, className)}
    >
      <Icon className={cn('mt-0.5 size-5 shrink-0', ICON_COLOUR[tone])} aria-hidden="true" />
      <div className="min-w-0 flex-1 space-y-2">
        <span className="sr-only">{word}: </span>
        {title ? <p className="text-body font-medium text-content">{title}</p> : null}
        <div className="max-w-prose text-body text-content-secondary">{children}</div>
        {action}
      </div>
    </div>
  );
}
