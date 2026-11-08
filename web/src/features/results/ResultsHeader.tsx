/**
 * Results header and tabs (KIRO_UI_UPGRADE_SPEC.md Section 7.4).
 *
 * The title, the industry, the run's status and how long it took, then the five tabs.
 *
 * The actions beside the title are composed by the page, because exporting, re-running and
 * deleting all need the run itself and the router; the header only places them, and marks them so
 * the print stylesheet leaves them out of a PDF.
 */

import { StatusChip, type StatusKind } from '@/components/StatusChip';
import { cn } from '@/lib/cn';
import { duration } from '@/lib/format';
import type { RunDetail } from '@/features/run/useRun';

export const TABS = [
  { key: 'overview', label: 'Overview' },
  { key: 'market', label: 'Market' },
  { key: 'competitors', label: 'Competitors' },
  { key: 'sources', label: 'Sources' },
  { key: 'details', label: 'Run details' },
] as const;

export type TabKey = (typeof TABS)[number]['key'];

/** The status chip for a finished run: the result's own status, or the run's when there is none. */
export function statusFor(run: RunDetail): { kind: StatusKind; label?: string } {
  if (run.state === 'cancelled') {
    return { kind: 'cancelled' };
  }
  const status = run.result?.status;
  if (status === 'complete') {
    return { kind: 'complete' };
  }
  if (status === 'partial') {
    return { kind: 'partial' };
  }
  return { kind: 'failed' };
}

export interface ResultsHeaderProps {
  run: RunDetail;
  active: TabKey;
  onChange: (tab: TabKey) => void;
  /** Counts shown beside a tab label where one is useful. */
  counts?: Partial<Record<TabKey, number>>;
  /** Export, "Edit and re-run" and Delete. Left out of a printed page. */
  actions?: React.ReactNode;
  /**
   * False for a run that produced nothing. A failed run has no market, no competitors and no
   * sources, so offering five tabs that each open an empty panel would be worse than offering none.
   */
  tabs?: boolean;
}

export function ResultsHeader({ run, active, onChange, counts, actions, tabs = true }: ResultsHeaderProps) {
  const status = statusFor(run);

  return (
    <div className="space-y-6">
      <div className="space-y-3">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <h1 className="min-w-0 font-condensed text-display">{run.title}</h1>
          {actions ? (
            <div data-print-hide className="flex flex-wrap items-center gap-2">
              {actions}
            </div>
          ) : null}
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <span className="rounded-pill border border-line bg-raised px-3 py-1 text-micro text-content-secondary">
            {run.industry}
          </span>
          <StatusChip kind={status.kind} {...(status.label ? { label: status.label } : {})} />
          <span className="tabular text-small text-content-muted">Took {duration(run.duration_s)}</span>
        </div>
      </div>

      {/* Section 6.5: underline tabs, moved through with the arrow keys. */}
      {tabs ? (
      <div role="tablist" aria-label="Result sections" className="flex gap-1 overflow-x-auto border-b border-line">
        {TABS.map((tab, index) => {
          const selected = tab.key === active;
          const count = counts?.[tab.key];
          return (
            <button
              key={tab.key}
              role="tab"
              type="button"
              id={`tab-${tab.key}`}
              aria-selected={selected}
              aria-controls={`panel-${tab.key}`}
              tabIndex={selected ? 0 : -1}
              onClick={() => onChange(tab.key)}
              onKeyDown={(event) => {
                if (event.key !== 'ArrowRight' && event.key !== 'ArrowLeft') {
                  return;
                }
                event.preventDefault();
                const step = event.key === 'ArrowRight' ? 1 : -1;
                const next = TABS[(index + step + TABS.length) % TABS.length];
                if (next) {
                  onChange(next.key);
                  document.getElementById(`tab-${next.key}`)?.focus();
                }
              }}
              className={cn(
                // Section 6.9: 44 px where a finger is used, the usual height from the small
                // breakpoint up.
                'shrink-0 border-b-2 px-3 py-2 text-body transition-colors duration-tab',
                'min-h-[44px] sm:min-h-0',
                selected
                  ? 'border-primary text-content'
                  : 'border-transparent text-content-secondary hover:text-content',
              )}
            >
              {tab.label}
              {count !== undefined ? <span className="tabular ml-2 text-small text-content-muted">{count}</span> : null}
            </button>
          );
        })}
      </div>
      ) : null}
    </div>
  );
}
