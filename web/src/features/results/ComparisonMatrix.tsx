/**
 * Comparison matrix (KIRO_UI_UPGRADE_SPEC.md Sections 6.4 rule 6, 8.4).
 *
 * Competitor rows against feature columns. Each cell is a symbol with a word beside it for
 * assistive technology and a tooltip for the pointer:
 *
 *   check     Evidence found
 *   question  Unclear
 *   dash      No evidence found in the sources
 *
 * A dash never means the feature does not exist, only that no source showed it, and the legend says
 * so. The first column stays in place while the table scrolls sideways, and a narrow screen gets a
 * visible hint that it scrolls (Section 2 finding 13).
 */

import { Check, HelpCircle, Minus } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';

import type { components } from '@/api/types.gen';
import { Citations } from '@/components/CitationChip';
import { cn } from '@/lib/cn';
import { MESSAGES } from '@/lib/format';
import { type SourceRecord, resolveSources } from '@/lib/results';

type Comparison = components['schemas']['Comparison'];
type CellStatus = components['schemas']['ComparisonCell']['status'];

export const CELL: Record<CellStatus, { Icon: LucideIcon; label: string; tone: string }> = {
  evidence_found: { Icon: Check, label: 'Evidence found', tone: 'text-success' },
  unclear: { Icon: HelpCircle, label: 'Unclear', tone: 'text-warning' },
  no_evidence_found: { Icon: Minus, label: 'No evidence found in the sources', tone: 'text-content-muted' },
};

/** A cell the backend left out is unclear, never "found" and never "absent". */
const FALLBACK: CellStatus = 'unclear';

export interface ComparisonMatrixProps {
  comparison: Comparison;
  sources: Map<string, SourceRecord>;
  onOpenSource: (key: string) => void;
}

export function ComparisonMatrix({ comparison, sources, onOpenSource }: ComparisonMatrixProps) {
  const features = comparison.features ?? [];
  const rows = comparison.rows ?? [];

  if (features.length === 0 || rows.length === 0) {
    return <p className="max-w-prose text-small text-content-muted">No feature comparison could be made.</p>;
  }

  return (
    <div className="space-y-4">
      <ul aria-label="What the symbols mean" className="flex flex-wrap gap-x-6 gap-y-2">
        {(Object.keys(CELL) as CellStatus[]).map((status) => {
          const { Icon, label, tone } = CELL[status];
          return (
            <li key={status} className="flex items-center gap-2 text-small text-content-secondary">
              <Icon className={cn('size-4 shrink-0', tone)} aria-hidden="true" />
              {label}
            </li>
          );
        })}
      </ul>

      <div className="relative overflow-x-auto rounded-panel border border-line" tabIndex={0} aria-label="Feature comparison, scrolls sideways">
        <table className="w-full border-collapse text-small">
          <caption className="sr-only">
            Each competitor against each compared feature. A dash means no source showed the feature, not that the
            feature is missing.
          </caption>
          <thead className="bg-raised">
            <tr>
              <th
                scope="col"
                className="sticky left-0 z-10 min-w-[10rem] border-b border-r border-line bg-raised px-3 py-2 text-left font-medium text-content-secondary"
              >
                Competitor
              </th>
              {features.map((feature) => (
                <th
                  key={feature}
                  scope="col"
                  className="min-w-[8rem] border-b border-line px-3 py-2 text-left align-bottom font-medium text-content-secondary"
                >
                  {feature}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.competitor} className="border-b border-line last:border-b-0">
                <th
                  scope="row"
                  className="sticky left-0 z-10 border-r border-line bg-surface px-3 py-2 text-left font-medium text-content"
                >
                  {row.competitor}
                </th>
                {features.map((feature) => {
                  const cell = (row.cells ?? []).find((entry) => entry.feature === feature);
                  const status = cell?.status ?? FALLBACK;
                  const { Icon, label, tone } = CELL[status];
                  return (
                    <td key={feature} className="bg-surface px-3 py-2" title={label}>
                      <span className="inline-flex flex-wrap items-center gap-1">
                        <Icon className={cn('size-4 shrink-0', tone)} aria-hidden="true" />
                        <span className="sr-only">{label}</span>
                        <Citations
                          sources={resolveSources(sources, 'competitors', cell?.source_ids)}
                          onOpen={onOpenSource}
                        />
                      </span>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-micro text-content-muted lg:hidden">Scroll sideways to see every feature.</p>
      <p className="max-w-prose text-small text-content-muted">{MESSAGES.gapCaveat}</p>
    </div>
  );
}
