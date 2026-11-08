/**
 * Feature coverage (KIRO_UI_UPGRADE_SPEC.md Section 9, chart 2 of 3).
 *
 * One horizontal bar per feature in the primary colour, labelled "x of n", sorted ascending so the
 * features with the least evidence, which are where a gap might be, come first. The same numbers
 * follow as a table, which is the accessible alternative Section 9 requires.
 *
 * The counts are `feature_coverage` from the backend, which counts the comparison cells marked
 * `evidence_found` (agents/competitor_checks.build_comparison). Nothing is counted here. A low count
 * means no source showed the feature, not that the feature does not exist (Section 8.4).
 */

import type { components } from '@/api/types.gen';
import { cn } from '@/lib/cn';
import { MESSAGES } from '@/lib/format';

type Coverage = components['schemas']['FeatureCoverage'];

export interface FeatureCoverageProps {
  coverage: Coverage[];
  /** How many competitors were compared: the "n" in "x of n". */
  competitors: number;
  className?: string;
}

/** Ascending by count, then alphabetical, so the order is stable from one render to the next. */
export function sortCoverage(coverage: Coverage[]): Coverage[] {
  return [...coverage].sort(
    (a, b) => a.competitors_with_evidence - b.competitors_with_evidence || a.feature.localeCompare(b.feature),
  );
}

export function FeatureCoverage({ coverage, competitors, className }: FeatureCoverageProps) {
  const rows = sortCoverage(coverage);

  if (rows.length === 0 || competitors === 0) {
    return (
      <div className={cn('rounded-panel border border-line bg-surface p-6', className)}>
        <h3>Feature coverage</h3>
        <p className="mt-2 max-w-prose text-small text-content-muted">No feature comparison could be made.</p>
      </div>
    );
  }

  return (
    <section
      aria-labelledby="feature-coverage-heading"
      className={cn('space-y-4 rounded-panel border border-line bg-surface p-6', className)}
    >
      <div className="space-y-1">
        <h3 id="feature-coverage-heading">Feature coverage</h3>
        <p className="max-w-prose text-small text-content-muted">
          How many of the {competitors} competitors show evidence of each feature. Fewest first.
        </p>
      </div>

      {/* The bars repeat the table below, so they are hidden from assistive technology. */}
      <ul aria-hidden="true" className="space-y-3">
        {rows.map((row) => (
          <li key={row.feature} className="space-y-1">
            <div className="flex items-baseline justify-between gap-4">
              <span className="min-w-0 truncate text-small text-content-secondary" title={row.feature}>
                {row.feature}
              </span>
              <span className="tabular shrink-0 text-small text-content">
                {row.competitors_with_evidence} of {competitors}
              </span>
            </div>
            <div className="h-2 w-full overflow-hidden rounded-pill bg-raised">
              <div
                className="h-full rounded-pill bg-primary"
                style={{ width: `${Math.min(row.competitors_with_evidence / competitors, 1) * 100}%` }}
              />
            </div>
          </li>
        ))}
      </ul>

      <table className="w-full border-t border-line text-small">
        <caption className="sr-only">
          Competitors with evidence of each feature, out of {competitors}, fewest first.
        </caption>
        <thead>
          <tr className="text-content-secondary">
            <th scope="col" className="py-2 text-left font-medium">
              Feature
            </th>
            <th scope="col" className="py-2 text-right font-medium">
              Competitors with evidence
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.feature} className="border-t border-line">
              <th scope="row" className="py-2 pr-4 text-left font-normal text-content">
                {row.feature}
              </th>
              <td className="tabular py-2 text-right text-content">
                {row.competitors_with_evidence} of {competitors}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <p className="max-w-prose text-small text-content-muted">{MESSAGES.gapCaveat}</p>
    </section>
  );
}
