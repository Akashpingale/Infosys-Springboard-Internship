/**
 * Empty state (KIRO_UI_UPGRADE_SPEC.md Section 6.5): an icon, one sentence saying what is missing,
 * and at most one action. It never apologises and never blames the user.
 */

import { Inbox } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';

import { cn } from '@/lib/cn';

export interface EmptyStateProps {
  /** One sentence on what is missing. */
  message: string;
  icon?: LucideIcon;
  action?: React.ReactNode;
  className?: string;
}

export function EmptyState({ message, icon: Icon = Inbox, action, className }: EmptyStateProps) {
  return (
    <div
      className={cn(
        'flex flex-col items-start gap-3 rounded-panel border border-line bg-surface p-6',
        className,
      )}
    >
      <Icon className="size-5 text-content-muted" aria-hidden="true" />
      <p className="max-w-prose text-body text-content-secondary">{message}</p>
      {action}
    </div>
  );
}
