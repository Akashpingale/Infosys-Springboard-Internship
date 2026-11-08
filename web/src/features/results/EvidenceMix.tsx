/**
 * Evidence mix (KIRO_UI_UPGRADE_SPEC.md Section 9, chart 1 of 3).
 *
 * One horizontal stacked bar: how many labelled findings are sourced, interpreted, taken from the
 * founder's words or assumed. The four basis colours in the fixed order of Section 6.2, a 2 px gap
 * between segments, counts labelled directly, a legend, and the same numbers as a table beneath,
 * which is the accessible alternative Section 9 requires.
 *
 * The counts are read from the checked result, so they match the sourced share the backend used
 * for the evidence strength.
 */

import { BASIS_LABELS, type Basis } from '@/components/BasisChip';
import { cn } from '@/lib/cn';

const COLOUR: Record<Basis, string> = {
  sourced: 'bg-sourced',
  ai_interpretation: 'bg-interpretation',
  user_provided: 'bg-provided',
  assumption: 'bg-assumption',
};

export interface EvidenceMixProps {
  counts: { basis: Basis; count: number }[];
  className?: string;
}

export function EvidenceMix({ counts, className }: EvidenceMixProps) {
  const total = counts.reduce((sum, entry) => sum + entry.count, 0);
  const present = counts.filter((entry) => entry.count > 0);

  if (total === 0) {
    return (
      <div className={cn('rounded-panel border border-line bg-surface p-6', className)}>
        <h3>Evidence mix</h3>
        <p className="mt-2 max-w-prose text-small text-content-muted">
          No labelled findings in this run, so there is no mix to show.
        </p>
      </div>
    );
  }

  return (
    <section aria-labelledby="evidence-mix-heading" className={cn('space-y-4 rounded-panel border border-line bg-surface p-6', className)}>
      <div className="space-y-1">
        <h3 id="evidence-mix-heading">Evidence mix</h3>
        <p className="max-w-prose text-small text-content-muted">
          How the {total} labelled findings in this result are grounded.
        </p>
      </div>

      {/* The bar is decoration over the table below, so it is hidden from assistive technology. */}
      <div aria-hidden="true" className="flex h-6 w-full gap-0.5 overflow-hidden rounded-pill">
        {present.map(({ basis, count }) => (
          <div
            key={basis}
            className={cn('h-full', COLOUR[basis])}
            style={{ width: `${(count / total) * 100}%` }}
            title={`${BASIS_LABELS[basis]}: ${count}`}
          />
        ))}
      </div>

      <ul aria-hidden="true" className="flex flex-wrap gap-x-6 gap-y-2">
        {counts.map(({ basis, count }) => (
          <li key={basis} className="flex items-center gap-2 text-small text-content-secondary">
            <span className={cn('size-3 shrink-0 rounded-sm', COLOUR[basis])} />
            {BASIS_LABELS[basis]}
            <span className="tabular text-content">{count}</span>
          </li>
        ))}
      </ul>

      <table className="w-full border-t border-line text-small">
        <caption className="sr-only">
          Labelled findings by how they are grounded, out of {total}.
        </caption>
        <thead>
          <tr className="text-content-secondary">
            <th scope="col" className="py-2 text-left font-medium">
              Basis
            </th>
            <th scope="col" className="py-2 text-right font-medium">
              Findings
            </th>
            <th scope="col" className="py-2 text-right font-medium">
              Share
            </th>
          </tr>
        </thead>
        <tbody>
          {counts.map(({ basis, count }) => (
            <tr key={basis} className="border-t border-line">
              <th scope="row" className="py-2 text-left font-normal text-content">
                {BASIS_LABELS[basis]}
              </th>
              <td className="tabular py-2 text-right text-content">{count}</td>
              <td className="tabular py-2 text-right text-content-secondary">
                {Math.round((count / total) * 100)}%
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
