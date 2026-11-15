/**
 * Overview tab (KIRO_UI_UPGRADE_SPEC.md Sections 7.4, 8.5 and 8.6).
 *
 * What the reader sees first: a summary whose every line carries its own sources, four tiles, the
 * takeaways, what still needs checking, the evidence mix, and the quality notes folded away.
 *
 * Every value comes from the result. A figure the sources did not give is shown as unavailable with
 * the reason (Section 6.8), never as a zero or a dash on its own.
 */

import { ListChecks } from 'lucide-react';

import { Citations } from '@/components/CitationChip';
import { MetricTile } from '@/components/MetricTile';
import { EvidenceMix } from '@/features/results/EvidenceMix';
import { QualityNotes } from '@/features/results/QualityNotes';
import { MISSING, MESSAGES, count } from '@/lib/format';
import {
  basisCounts,
  competitorCounts,
  marketSizeSummary,
  type Claim,
  type PipelineResult,
  type SourceRecord,
  resolveSources,
} from '@/lib/results';

const STRENGTH_WORD = { strong: 'Strong', moderate: 'Moderate', limited: 'Limited' } as const;

const STRATEGY_PART_NAMES = [
  ['swot', 'the SWOT and risk review'],
  ['mvp', 'the MVP plan'],
  ['gtm', 'the go-to-market plan'],
] as const;

export interface StrategyTile {
  state: 'generated' | 'partly' | 'none';
  value: string | null;
  detail: string;
}

function inWords(parts: string[]): string {
  return parts.length <= 1 ? parts.join('') : `${parts.slice(0, -1).join(', ')} and ${parts[parts.length - 1]}`;
}

/**
 * Milestone 3, Section 14.5: the Strategy tile. Its value counts what the strategy holds ("7 risks,
 * 5 features for the first release") and its chip says whether all three parts are there.
 */
export function strategyTile(result: PipelineResult): StrategyTile {
  const present = STRATEGY_PART_NAMES.filter(([field]) => Boolean(result[field]));
  if (present.length === 0) {
    return { state: 'none', value: null, detail: 'There is no SWOT, MVP plan or go-to-market plan yet.' };
  }
  const values: string[] = [];
  if (result.swot) {
    values.push(count((result.swot.risks ?? []).length, 'risk'));
  }
  if (result.mvp) {
    const first = (result.mvp.features ?? []).filter((feature) => feature.tier === 'mvp').length;
    values.push(`${count(first, 'feature')} for the first release`);
  }
  const value = values.length > 0 ? values.join(', ') : 'Go-to-market plan';
  if (present.length === STRATEGY_PART_NAMES.length) {
    return { state: 'generated', value, detail: 'SWOT and risk review, MVP plan and go-to-market plan.' };
  }
  const absent = STRATEGY_PART_NAMES.filter(([field]) => !result[field]).map(([, name]) => name);
  return { state: 'partly', value, detail: `Not generated: ${inWords(absent)}.` };
}

const STRATEGY_STATUS = {
  generated: { kind: 'complete', label: 'Generated' },
  partly: { kind: 'partial', label: 'Partly generated' },
  none: { kind: 'unavailable', label: 'Not generated' },
} as const;

export interface OverviewTabProps {
  result: PipelineResult;
  sources: Map<string, SourceRecord>;
  claims: Claim[];
  onOpenSource: (key: string) => void;
}

export function OverviewTab({ result, sources, claims, onOpenSource }: OverviewTabProps) {
  const strength = result.evidence_strength;
  const size = marketSizeSummary(result);
  const competitors = competitorCounts(result);
  const priority = result.market?.priority_segment;
  const counts = basisCounts(claims);
  const strategy = strategyTile(result);

  // Section 7.4: the takeaways are the labelled opportunities and differentiation items, which the
  // agents already checked, shown with their own basis and sources.
  // These lists are optional in the schema, so a result saved before they existed has none.
  const summary = result.executive_summary ?? [];
  const verifyNext = result.verify_next ?? [];
  const notices = result.notices ?? [];

  const takeaways = [
    ...(result.market?.opportunities ?? []).map((item) => ({ item, analysis: 'market' as const })),
    ...(result.competitors?.differentiation_opportunities ?? []).map((item) => ({
      item,
      analysis: 'competitors' as const,
    })),
  ].slice(0, 5);

  return (
    <div className="space-y-8">
      {summary.length > 0 ? (
        <section aria-labelledby="summary-heading" className="space-y-3 rounded-panel border border-line bg-surface p-6">
          <h2 id="summary-heading">Summary</h2>
          <ul className="space-y-3">
            {summary.map((line, index) => (
              <li key={`${line.topic}-${index}`} className="max-w-prose text-body text-content-secondary">
                {line.text}{' '}
                <Citations
                  sources={resolveSources(sources, line.analysis, line.source_ids)}
                  basis={line.basis ?? null}
                  onOpen={onOpenSource}
                />
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {strength ? (
          <MetricTile
            label="Evidence strength"
            value={STRENGTH_WORD[strength.label]}
            detail={strength.caption}
          />
        ) : (
          <MetricTile label="Evidence strength" missing="Not rated" detail="Neither analysis finished." />
        )}

        {size.sourced ? (
          <MetricTile
            label={`Market size (${size.sourced.label})`}
            value={size.sourced.value}
            status={{ kind: 'sourced' }}
            {...(size.sourced.note ? { detail: size.sourced.note } : {})}
          />
        ) : (
          <MetricTile
            label="Market size"
            missing={MISSING.marketSize}
            status={{ kind: 'unavailable' }}
            detail={MESSAGES.marketSizeUnavailable}
          />
        )}

        {result.competitors ? (
          <MetricTile
            label="Competitors found"
            value={competitors.total}
            detail={`${competitors.direct} direct, ${competitors.indirect} indirect and ${competitors.emerging} emerging.`}
          />
        ) : (
          <MetricTile label="Competitors found" missing="Not analysed" detail="The competitor stage did not finish." />
        )}

        {priority ? (
          <MetricTile label="Priority segment" value={priority.segment_name} detail={priority.rationale} />
        ) : (
          <MetricTile
            label="Priority segment"
            missing="None chosen"
            detail="No segment stood out from the evidence."
          />
        )}

        {strategy.value !== null ? (
          <MetricTile
            label="Strategy"
            value={strategy.value}
            status={STRATEGY_STATUS[strategy.state]}
            detail={strategy.detail}
          />
        ) : (
          <MetricTile
            label="Strategy"
            missing="No strategy yet"
            status={STRATEGY_STATUS[strategy.state]}
            detail={strategy.detail}
          />
        )}
      </div>

      {strength ? (
        <section aria-labelledby="strength-heading" className="space-y-4 rounded-panel border border-line bg-surface p-6">
          <div className="space-y-1">
            <h3 id="strength-heading">How the evidence strength is worked out</h3>
            <p className="max-w-prose text-small text-content-muted">{strength.caption}</p>
          </div>
          <ul className="space-y-3">
            {strength.components.map((component) => (
              <li key={component.key} className="space-y-1">
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <span className="text-body text-content">{component.label}</span>
                  <span className="tabular text-small text-content-muted">
                    weight {Math.round(component.weight * 100)}%
                  </span>
                </div>
                <div aria-hidden="true" className="h-2 w-full overflow-hidden rounded-pill bg-raised">
                  <div className="h-full rounded-pill bg-primary" style={{ width: `${component.value * 100}%` }} />
                </div>
                <p className="max-w-prose text-small text-content-secondary">{component.detail}</p>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <div className="grid gap-6 lg:grid-cols-2">
        <section aria-labelledby="takeaways-heading" className="space-y-3 rounded-panel border border-line bg-surface p-6">
          <h3 id="takeaways-heading">Key takeaways</h3>
          {takeaways.length === 0 ? (
            <p className="max-w-prose text-small text-content-muted">{MISSING.none}</p>
          ) : (
            <ul className="space-y-3">
              {takeaways.map(({ item, analysis }, index) => (
                <li key={`${analysis}-${index}`} className="max-w-prose text-body text-content-secondary">
                  {item.text}{' '}
                  <Citations
                    sources={resolveSources(sources, analysis, item.source_ids)}
                    basis={item.basis}
                    onOpen={onOpenSource}
                  />
                </li>
              ))}
            </ul>
          )}
        </section>

        <section aria-labelledby="verify-heading" className="space-y-3 rounded-panel border border-line bg-surface p-6">
          <div className="flex items-center gap-2">
            <ListChecks className="size-5 text-content-muted" aria-hidden="true" />
            <h3 id="verify-heading">What to verify next</h3>
          </div>
          {verifyNext.length === 0 ? (
            <p className="max-w-prose text-small text-content-muted">
              Nothing came back unavailable or uncertain in this run.
            </p>
          ) : (
            <ul className="space-y-3">
              {verifyNext.map((item, index) => (
                <li key={`${item.topic}-${index}`} className="flex items-start gap-3">
                  {/* A checklist to work through, so each line gets its own box. The box is 20 px
                      and its label is the rest of the target, which is taller than 44 px. */}
                  <input
                    type="checkbox"
                    id={`verify-${index}`}
                    className="mt-3 size-5 shrink-0 accent-primary sm:mt-1 sm:size-4"
                  />
                  <label
                    htmlFor={`verify-${index}`}
                    className="flex min-h-[44px] max-w-prose items-center text-body text-content-secondary sm:min-h-0"
                  >
                    {item.text}{' '}
                    <Citations
                      sources={resolveSources(sources, item.analysis, item.source_ids)}
                      onOpen={onOpenSource}
                    />
                  </label>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <EvidenceMix counts={counts} />
        <QualityNotes notices={notices} className="self-start" />
      </div>
    </div>
  );
}
