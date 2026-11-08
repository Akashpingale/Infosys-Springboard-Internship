/**
 * Competitors tab (KIRO_UI_UPGRADE_SPEC.md Sections 7.4, 8.4 and 9, Prompt H).
 *
 * In order: filter chips by type, the competitor cards in two columns, the comparison matrix, the
 * feature coverage chart with its table, the possible gaps as hypothesis cards, the differentiation
 * opportunities, and the searches that were run, folded away.
 *
 * Everything comes from the checked competitor analysis. The counts on the filter chips are counted
 * from the competitors the backend kept. A gap is always shown as a hypothesis with its caveat, and
 * a dash in the matrix is never presented as "the feature does not exist".
 */

import { ChevronRight, Lightbulb } from 'lucide-react';
import * as React from 'react';

import type { components } from '@/api/types.gen';
import { Alert } from '@/components/Alert';
import { BasisChip } from '@/components/BasisChip';
import { Citations } from '@/components/CitationChip';
import { ClaimList, TextWithCitations } from '@/components/Claim';
import { EmptyState } from '@/components/EmptyState';
import { CompetitorCard, TYPE_LABEL, type CompetitorType } from '@/features/results/CompetitorCard';
import { ComparisonMatrix } from '@/features/results/ComparisonMatrix';
import { FeatureCoverage } from '@/features/results/FeatureCoverage';
import { cn } from '@/lib/cn';
import { MESSAGES, MISSING } from '@/lib/format';
import { type PipelineResult, type SourceRecord, resolveSources, stageProblem } from '@/lib/results';

type Gap = components['schemas']['MarketGap'];

export type Filter = 'all' | CompetitorType;
const FILTERS: Filter[] = ['all', 'direct', 'indirect', 'emerging'];
const FILTER_LABEL: Record<Filter, string> = { all: 'All', ...TYPE_LABEL };

const CONFIDENCE: Record<Gap['confidence'], string> = {
  low: 'Low confidence',
  medium: 'Medium confidence',
};

function GapCard({
  gap,
  sources,
  onOpenSource,
}: {
  gap: Gap;
  sources: Map<string, SourceRecord>;
  onOpenSource: (key: string) => void;
}) {
  const related = gap.related_features ?? [];
  return (
    <article className="space-y-3 rounded-panel border border-line bg-surface p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <span className="inline-flex items-center gap-2 text-micro text-content-muted">
          <Lightbulb className="size-3.5" aria-hidden="true" />
          Hypothesis
        </span>
        <span
          className={cn(
            'inline-flex h-6 items-center rounded-pill border px-3 text-micro',
            gap.confidence === 'medium'
              ? 'border-info-border bg-info-bg text-content'
              : 'border-line bg-raised text-content-secondary',
          )}
        >
          {CONFIDENCE[gap.confidence]}
        </span>
      </div>
      <p className="max-w-prose text-body text-content">
        {gap.description}{' '}
        <Citations sources={resolveSources(sources, 'competitors', gap.source_ids)} onOpen={onOpenSource} />
      </p>
      <BasisChip basis={gap.basis} />
      {related.length > 0 ? (
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-small text-content-muted">Related features</span>
          {related.map((feature) => (
            <span
              key={feature}
              className="rounded-pill border border-line bg-raised px-3 py-0.5 text-micro text-content-secondary"
            >
              {feature}
            </span>
          ))}
        </div>
      ) : null}
      {/* Section 6.7: every gap carries the caveat, in the specified words. */}
      <p className="border-t border-line pt-3 text-small text-content-muted">{MESSAGES.gapCaveat}</p>
    </article>
  );
}

export interface CompetitorsTabProps {
  result: PipelineResult;
  sources: Map<string, SourceRecord>;
  onOpenSource: (key: string) => void;
}

export function CompetitorsTab({ result, sources, onOpenSource }: CompetitorsTabProps) {
  const [filter, setFilter] = React.useState<Filter>('all');
  const analysis = result.competitors;

  // Section 6.8: a stage that did not finish gets a panel saying which one and why.
  if (!analysis) {
    const reason = stageProblem(result, 'competitor_analysis');
    return (
      <Alert tone="warning" title="Comparing competitors did not finish">
        {reason ?? 'The competitor analysis did not run for this validation, so there is nothing to show here.'}
      </Alert>
    );
  }

  const competitors = analysis.competitors ?? [];
  const counts: Record<Filter, number> = {
    all: competitors.length,
    direct: competitors.filter((entry) => entry.type === 'direct').length,
    indirect: competitors.filter((entry) => entry.type === 'indirect').length,
    emerging: competitors.filter((entry) => entry.type === 'emerging').length,
  };
  const shown = filter === 'all' ? competitors : competitors.filter((entry) => entry.type === filter);
  const gaps = analysis.market_gaps ?? [];
  const queries = analysis.queries_used ?? [];
  const notes = analysis.data_quality.notes ?? [];

  return (
    <div className="space-y-12">
      <section aria-labelledby="competitors-heading" className="space-y-4">
        <div className="space-y-1">
          <h2 id="competitors-heading">Competitors</h2>
          <p className="max-w-prose text-small text-content-muted">
            Only competitors that a cited source names, or that you named, are listed.
          </p>
        </div>

        {/* Section 7.4: filter chips. A radio group, because exactly one filter applies. */}
        <div role="radiogroup" aria-label="Show competitors by type" className="flex flex-wrap gap-2">
          {FILTERS.map((key) => {
            const active = filter === key;
            return (
              <button
                key={key}
                type="button"
                role="radio"
                aria-checked={active}
                disabled={key !== 'all' && counts[key] === 0}
                onClick={() => setFilter(key)}
                className={cn(
                  'inline-flex h-8 min-h-[44px] items-center gap-2 rounded-pill border px-3 text-small sm:min-h-8',
                  'transition-colors duration-tab disabled:cursor-not-allowed disabled:opacity-50',
                  active
                    ? 'border-primary bg-info-bg text-content'
                    : 'border-line bg-surface text-content-secondary hover:bg-raised hover:text-content',
                )}
              >
                {FILTER_LABEL[key]}
                <span className="tabular text-micro text-content-muted">{counts[key]}</span>
              </button>
            );
          })}
        </div>

        <p aria-live="polite" className="sr-only">
          {`Showing ${shown.length} ${shown.length === 1 ? 'competitor' : 'competitors'}.`}
        </p>

        {shown.length === 0 ? (
          <EmptyState message={`No ${FILTER_LABEL[filter].toLowerCase()} competitors were found in the sources.`} />
        ) : (
          <div className="grid gap-4 lg:grid-cols-2">
            {shown.map((competitor) => (
              <CompetitorCard
                key={competitor.name}
                competitor={competitor}
                sources={sources}
                onOpenSource={onOpenSource}
              />
            ))}
          </div>
        )}
      </section>

      <section aria-labelledby="comparison-heading" className="space-y-4">
        <div className="space-y-1">
          <h2 id="comparison-heading">Feature comparison</h2>
          <p className="max-w-prose text-small text-content-muted">
            Your idea&rsquo;s key features and the features seen in the competitor data, checked against each
            competitor&rsquo;s sources.
          </p>
        </div>
        <ComparisonMatrix comparison={analysis.comparison} sources={sources} onOpenSource={onOpenSource} />
      </section>

      <FeatureCoverage coverage={analysis.comparison.feature_coverage ?? []} competitors={competitors.length} />

      <section aria-labelledby="gaps-heading" className="space-y-4">
        <div className="space-y-1">
          <h2 id="gaps-heading">Possible gaps</h2>
          <p className="max-w-prose text-small text-content-muted">
            Hypotheses to test, not findings. Confidence is never rated above medium.
          </p>
        </div>
        {gaps.length === 0 ? (
          <p className="max-w-prose text-small text-content-muted">{MISSING.none}</p>
        ) : (
          <div className="grid gap-4 lg:grid-cols-2">
            {gaps.map((gap, index) => (
              <GapCard key={`${index}-${gap.description.slice(0, 24)}`} gap={gap} sources={sources} onOpenSource={onOpenSource} />
            ))}
          </div>
        )}
      </section>

      <section aria-labelledby="differentiation-heading" className="space-y-4">
        <h2 id="differentiation-heading">Differentiation opportunities</h2>
        <div className="rounded-panel border border-line bg-surface p-6">
          <ClaimList
            items={analysis.differentiation_opportunities ?? []}
            analysis="competitors"
            sources={sources}
            onOpenSource={onOpenSource}
            empty={MISSING.none}
          />
        </div>
      </section>

      <section aria-labelledby="competitor-notes-heading" className="space-y-4">
        <div className="space-y-1">
          <h2 id="competitor-notes-heading">Evidence notes</h2>
          <p className="max-w-prose text-small text-content-muted">
            The competitor evidence was rated {analysis.data_quality.evidence_level}. These are the points it could not
            settle.
          </p>
        </div>
        <div className="space-y-4 rounded-panel border border-line bg-surface p-6">
          {notes.length === 0 ? (
            <p className="text-small text-content-muted">The analysis recorded no open points.</p>
          ) : (
            <ul className="list-disc space-y-2 pl-5 text-body text-content-secondary">
              {notes.map((note) => (
                <li key={note} className="max-w-prose">
                  <TextWithCitations text={note} analysis="competitors" sources={sources} onOpenSource={onOpenSource} />
                </li>
              ))}
            </ul>
          )}
          {(analysis.caveats ?? []).map((caveat) => (
            <p key={caveat} className="border-t border-line pt-4 text-small text-content-muted">
              {caveat}
            </p>
          ))}
        </div>
      </section>

      {/* Section 7.4: "Searches run", collapsed. */}
      <section aria-labelledby="searches-heading" className="rounded-panel border border-line bg-surface">
        <details className="group">
          <summary className="flex cursor-pointer items-center gap-3 p-4 text-body text-content">
            <ChevronRight
              className="size-4 shrink-0 transition-transform duration-tab group-open:rotate-90"
              aria-hidden="true"
            />
            <span id="searches-heading" className="flex-1">
              Searches run for this analysis
            </span>
            <span className="tabular text-small text-content-muted">{queries.length}</span>
          </summary>
          <div className="border-t border-line p-4">
            {queries.length === 0 ? (
              <p className="text-small text-content-muted">No targeted searches were run.</p>
            ) : (
              <ol className="list-decimal space-y-2 pl-5">
                {queries.map((query) => (
                  <li key={query} className="break-words font-mono text-small text-content-secondary">
                    {query}
                  </li>
                ))}
              </ol>
            )}
          </div>
        </details>
      </section>
    </div>
  );
}
