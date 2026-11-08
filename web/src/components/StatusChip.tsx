/**
 * Status chip (KIRO_UI_UPGRADE_SPEC.md Sections 6.2 and 6.5).
 *
 * Always an icon and a word, never colour alone, so it reads the same to someone who cannot tell
 * the colours apart. The words are the ones the backend's statuses map to.
 */

import { AlertTriangle, CheckCircle2, CircleDashed, Info, Loader2, XCircle, XOctagon } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';

import { cn } from '@/lib/cn';

export type StatusKind =
  | 'complete'
  | 'partial'
  | 'failed'
  | 'running'
  | 'queued'
  | 'cancelled'
  | 'info'
  | 'sourced'
  | 'estimate'
  | 'unavailable';

interface Appearance {
  label: string;
  Icon: LucideIcon;
  className: string;
  spin?: boolean;
}

const APPEARANCE: Record<StatusKind, Appearance> = {
  complete: { label: 'Complete', Icon: CheckCircle2, className: 'bg-success-bg text-success border-success-border' },
  partial: { label: 'Partial', Icon: AlertTriangle, className: 'bg-warning-bg text-warning border-warning-border' },
  failed: { label: 'Failed', Icon: XCircle, className: 'bg-danger-bg text-danger border-danger-border' },
  running: { label: 'Running', Icon: Loader2, className: 'bg-info-bg text-info border-info-border', spin: true },
  queued: { label: 'Queued', Icon: CircleDashed, className: 'bg-raised text-content-secondary border-line' },
  cancelled: { label: 'Cancelled', Icon: XOctagon, className: 'bg-raised text-content-secondary border-line' },
  info: { label: 'Note', Icon: Info, className: 'bg-info-bg text-info border-info-border' },
  // Figure statuses (Sections 6.1 principle 4 and 6.8): an unavailable figure is shown plainly in a
  // neutral tone, never as an alarm.
  sourced: { label: 'Sourced', Icon: CheckCircle2, className: 'bg-success-bg text-success border-success-border' },
  estimate: { label: 'Estimate', Icon: AlertTriangle, className: 'bg-warning-bg text-warning border-warning-border' },
  unavailable: { label: 'Unavailable', Icon: CircleDashed, className: 'bg-raised text-content-secondary border-line' },
};

export interface StatusChipProps {
  kind: StatusKind;
  /** Replaces the default word, for a run state the API words differently. */
  label?: string;
  className?: string;
}

export function StatusChip({ kind, label, className }: StatusChipProps) {
  const { label: fallback, Icon, className: tone, spin } = APPEARANCE[kind];
  return (
    <span
      className={cn(
        'inline-flex h-6 items-center gap-2 rounded-pill border px-3 text-micro',
        tone,
        className,
      )}
    >
      <Icon className={cn('size-3.5 shrink-0', spin && 'animate-spin')} aria-hidden="true" />
      {label ?? fallback}
    </span>
  );
}
