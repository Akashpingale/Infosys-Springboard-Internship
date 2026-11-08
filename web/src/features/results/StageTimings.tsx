/**
 * Stage timings (KIRO_UI_UPGRADE_SPEC.md Section 9, chart 3 of 3).
 *
 * One stacked bar across the four stages, each segment as wide as its share of the time, with the
 * durations labelled, the total stated and the same numbers as a table beneath.
 *
 * The four segments are one hue in four steps rather than four different colours, because the
 * basis colours of Section 6.2 mean something else and must not be borrowed here. Nothing is
 * inferred: a stage that did not run has no segment and its row says what happened to it.
 */

import type { RunStage } from '@/features/run/useRun';
import { cn } from '@/lib/cn';
import { duration } from '@/lib/format';
import type { StageBar, StageTiming } from '@/lib/runDetails';

/**
 * One hue in four steps, in stage order.
 *
 * Each step is its own token. An opacity modifier such as `bg-primary/75` would be the obvious way
 * to write this, but these tokens hold a whole colour rather than channel numbers, so Tailwind
 * emits no rule for it at all and the segment would simply not be painted.
 */
export const SHADES = ['bg-step-1', 'bg-step-2', 'bg-step-3', 'bg-step-4'] as const;

/** The plain word for a stage's status, so the table never relies on colour (Section 6.9). */
const STATUS_WORD: Record<RunStage['status'], string> = {
  waiting: 'Did not start',
  running: 'Running',
  done: 'Done',
  skipped: 'Skipped',
  failed: 'Failed',
  cancelled: 'Cancelled',
};

function shade(index: number): string {
  return SHADES[index % SHADES.length] ?? 'bg-primary';
}

export interface StageTimingsProps {
  timing: StageTiming;
  className?: string;
}

export function StageTimings({ timing, className }: StageTimingsProps) {
  const { bars, total, totalFromResult } = timing;
  const measured = bars.filter((bar) => bar.seconds !== null && bar.seconds > 0);
  const scale = measured.reduce((sum, bar) => sum + (bar.seconds ?? 0), 0);

  return (
    <section
      aria-labelledby="stage-timings-heading"
      className={cn('space-y-4 rounded-panel border border-line bg-surface p-6', className)}
    >
      <div className="space-y-1">
        <h3 id="stage-timings-heading">Stage timings</h3>
        <p className="max-w-prose text-small text-content-muted">
          {measured.length === 0
            ? 'No stage recorded a duration for this run.'
            : totalFromResult
              ? `${duration(total)} in total, measured end to end by the pipeline.`
              : `${duration(total)} in total, added up from the stages.`}
        </p>
      </div>

      {measured.length > 0 ? (
        <>
          {/* The bar repeats the table below, so assistive technology is given the table instead. */}
          <div aria-hidden="true" className="flex h-6 w-full gap-0.5 overflow-hidden rounded-pill">
            {bars.map((bar, index) =>
              bar.seconds !== null && bar.seconds > 0 ? (
                <div
                  key={bar.key}
                  className={cn('h-full', shade(index))}
                  style={{ width: `${((bar.seconds ?? 0) / scale) * 100}%` }}
                  title={`${bar.label}: ${duration(bar.seconds)}`}
                />
              ) : null,
            )}
          </div>

          <ul aria-hidden="true" className="flex flex-wrap gap-x-6 gap-y-2">
            {bars.map((bar, index) => (
              <li key={bar.key} className="flex items-center gap-2 text-small text-content-secondary">
                <span className={cn('size-3 shrink-0 rounded-sm', shade(index))} />
                {bar.label}
                <span className="tabular text-content">{duration(bar.seconds)}</span>
              </li>
            ))}
          </ul>
        </>
      ) : null}

      <table className="w-full border-t border-line text-small">
        <caption className="sr-only">How long each stage took, and the total.</caption>
        <thead>
          <tr className="text-content-secondary">
            <th scope="col" className="py-2 text-left font-medium">
              Stage
            </th>
            <th scope="col" className="py-2 text-left font-medium">
              Status
            </th>
            <th scope="col" className="py-2 text-right font-medium">
              Time
            </th>
            <th scope="col" className="py-2 text-right font-medium">
              Share
            </th>
          </tr>
        </thead>
        <tbody>
          {bars.map((bar) => (
            <tr key={bar.key} className="border-t border-line">
              <th scope="row" className="py-2 pr-4 text-left font-normal text-content">
                {bar.label}
              </th>
              <td className="py-2 pr-4 text-content-secondary">{STATUS_WORD[bar.status]}</td>
              <td className="tabular py-2 text-right text-content">{duration(bar.seconds)}</td>
              <td className="tabular py-2 text-right text-content-secondary">
                {bar.seconds !== null && scale > 0 ? `${Math.round((bar.seconds / scale) * 100)}%` : '\u2014'}
              </td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr className="border-t border-line-strong">
            <th scope="row" className="py-2 pr-4 text-left font-medium text-content">
              Total
            </th>
            <td className="py-2" />
            <td className="tabular py-2 text-right font-medium text-content">{duration(total)}</td>
            <td className="py-2" />
          </tr>
        </tfoot>
      </table>
    </section>
  );
}

export type { StageBar };
