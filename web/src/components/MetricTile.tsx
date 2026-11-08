/**
 * Metric tile (KIRO_UI_UPGRADE_SPEC.md Sections 6.5 and 7.4).
 *
 * A label, one value, an optional status chip and one line of explanation. A value that the sources
 * did not give is shown in the muted colour with its reason, never as a zero (Section 6.8).
 */

import { StatusChip, type StatusKind } from '@/components/StatusChip';
import { cn } from '@/lib/cn';

export interface MetricTileProps {
  label: string;
  /** The figure or word to show. Give `missing` instead when nothing was found. */
  value?: React.ReactNode;
  /** Shown in place of a value, in the muted colour: "Unavailable", "Not found in the sources". */
  missing?: string;
  status?: { kind: StatusKind; label?: string };
  /** One line saying where the value came from, or why there is none. */
  detail?: string;
  /** Shown under the detail, for example the citation chips of a figure. */
  footer?: React.ReactNode;
  className?: string;
}

export function MetricTile({ label, value, missing, status, detail, footer, className }: MetricTileProps) {
  return (
    <div className={cn('rounded-panel border border-line bg-surface p-4', className)}>
      <div className="flex items-baseline justify-between gap-3">
        <h3 className="text-small font-medium text-content-secondary">{label}</h3>
        {status ? <StatusChip kind={status.kind} label={status.label} /> : null}
      </div>
      <p
        className={cn(
          'mt-2 font-condensed text-kpi tabular',
          missing !== undefined ? 'text-content-muted' : 'text-content',
        )}
      >
        {missing !== undefined ? missing : value}
      </p>
      {detail ? <p className="mt-1 text-small text-content-muted">{detail}</p> : null}
      {footer ? <div className="mt-2">{footer}</div> : null}
    </div>
  );
}
