/**
 * Market tab (KIRO_UI_UPGRADE_SPEC.md Section 7.4, Prompt G).
 *
 * A sticky section list on the left and the content on the right: industry overview, demand, the
 * TAM, SAM and SOM tiles with their broader markets beside them as context only, trends in four
 * columns by category, the segment cards with the priority one marked, and opportunities beside
 * limitations. The last section repeats what the evidence could not establish.
 *
 * Every claim carries its basis chip and its citation chips. Nothing here adds a figure: a value the
 * sources did not give is shown as unavailable with its reason (Section 6.8), and a figure for a
 * wider market is never shown as this idea's market size.
 */

import { Star } from 'lucide-react';
import * as React from 'react';

import type { components } from '@/api/types.gen';
import { Alert } from '@/components/Alert';
import { BasisChip } from '@/components/BasisChip';
import { Citations } from '@/components/CitationChip';
import { ClaimItem, ClaimList, TextWithCitations } from '@/components/Claim';
import { MetricTile } from '@/components/MetricTile';
import { StatusChip, type StatusKind } from '@/components/StatusChip';
import { cn } from '@/lib/cn';
import { MESSAGES, MISSING } from '@/lib/format';
import {
  FIGURE_LABELS,
  type PipelineResult,
  type SourceRecord,
  resolveSources,
  stageProblem,
} from '@/lib/results';

type Market = components['schemas']['MarketOpportunityResult'];
type MarketFigure = components['schemas']['MarketFigure'];
type Segment = components['schemas']['Segment'];
type Trend = components['schemas']['Trend'];

export const SECTIONS = [
  { id: 'market-overview', label: 'Industry overview' },
  { id: 'market-demand', label: 'Demand' },
  { id: 'market-size', label: 'Market size' },
  { id: 'market-trends', label: 'Trends' },
  { id: 'market-segments', label: 'Segments' },
  { id: 'market-opportunities', label: 'Opportunities and limitations' },
  { id: 'market-evidence', label: 'Evidence notes' },
] as const;

/** Section 7.4: four columns, in this order. */
const TREND_COLUMNS: { key: Trend['category']; label: string }[] = [
  { key: 'technology', label: 'Technology' },
  { key: 'consumer', label: 'Consumer' },
  { key: 'industry', label: 'Industry' },
  { key: 'business', label: 'Business' },
];

const SEGMENTATION: Record<Segment['segmentation_basis'], string> = {
  demographic: 'Demographic',
  business_type: 'Business type',
  location: 'Location',
  needs: 'Needs',
  behavior: 'Behaviour',
};

const LEVEL_WORD = { strong: 'strong', limited: 'limited', insufficient: 'insufficient' } as const;

export const MSG_BROADER =
  'Figures for a wider or different market, such as a whole industry. They are context only and are ' +
  'never used as this idea\u2019s TAM, SAM or SOM.';
export const MSG_ESTIMATE = 'Treat it as an estimate and verify it against its source.';
export const MSG_NO_TREND = 'None found in the sources.';

interface SectionProps {
  id: string;
  title: string;
  description?: string;
  children: React.ReactNode;
}

/** One section of the tab. Its heading takes focus when the section list jumps to it. */
function Section({ id, title, description, children }: SectionProps) {
  return (
    <section id={id} aria-labelledby={`${id}-heading`} className="scroll-mt-6 space-y-4">
      <div className="space-y-1">
        <h2 id={`${id}-heading`} tabIndex={-1} className="outline-none">
          {title}
        </h2>
        {description ? <p className="max-w-prose text-small text-content-muted">{description}</p> : null}
      </div>
      {children}
    </section>
  );
}

function figureStatus(figure: MarketFigure): StatusKind {
  if (figure.status === 'sourced') {
    return 'sourced';
  }
  return figure.status === 'estimate_needs_verification' ? 'estimate' : 'unavailable';
}

interface FigureTileProps {
  label: string;
  figure: MarketFigure | undefined;
  sources: Map<string, SourceRecord>;
  onOpenSource: (key: string) => void;
}

/** One of TAM, SAM, SOM (Section 2 finding 12): a status chip and a one-line reason, never a bare "Not available". */
function FigureTile({ label, figure, sources, onOpenSource }: FigureTileProps) {
  const chips = (
    <Citations sources={resolveSources(sources, 'market', figure?.source_ids)} onOpen={onOpenSource} />
  );
  if (!figure || figure.status === 'unavailable' || !figure.value) {
    return (
      <MetricTile
        label={label}
        missing={MISSING.marketSize}
        status={{ kind: 'unavailable' }}
        detail={figure?.note || MESSAGES.marketSizeUnavailable}
      />
    );
  }
  const note = figure.note ?? '';
  return (
    <MetricTile
      label={label}
      value={figure.value}
      status={{ kind: figureStatus(figure) }}
      detail={figure.status === 'sourced' ? note : [note, MSG_ESTIMATE].filter(Boolean).join(' ')}
      footer={chips}
    />
  );
}

function SegmentCard({
  segment,
  priority,
  sources,
  onOpenSource,
}: {
  segment: Segment;
  priority: Market['priority_segment'];
  sources: Map<string, SourceRecord>;
  onOpenSource: (key: string) => void;
}) {
  const isPriority = priority?.segment_name === segment.name;
  const needs = segment.needs ?? [];
  const pains = segment.pain_points ?? [];
  // aria-labelledby reads a space as a separator between two ids, so a name like "Smallholder
  // Farmers" cannot be used as an id directly; React's useId gives one that is always safe.
  const headingId = React.useId();
  return (
    <article
      aria-labelledby={headingId}
      className={cn(
        'space-y-4 rounded-panel border bg-surface p-6',
        isPriority ? 'border-primary' : 'border-line',
      )}
    >
      {/* Section 6.4 rule 4: the title on the left, the meta on the right. */}
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h3 id={headingId}>{segment.name}</h3>
        <div className="flex flex-wrap items-center gap-2">
          {isPriority ? (
            <span className="inline-flex h-6 items-center gap-2 rounded-pill border border-primary px-3 text-micro text-content">
              <Star className="size-3.5 text-primary" aria-hidden="true" />
              Priority segment
            </span>
          ) : null}
          <span className="rounded-pill border border-line bg-raised px-3 py-0.5 text-micro text-content-secondary">
            By {SEGMENTATION[segment.segmentation_basis].toLowerCase()}
          </span>
        </div>
      </div>

      <p className="max-w-prose text-body text-content-secondary">
        {segment.description}{' '}
        <Citations sources={resolveSources(sources, 'market', segment.source_ids)} onOpen={onOpenSource} />
      </p>

      <div className="space-y-2">
        <h4 className="text-small font-medium text-content">Needs</h4>
        {needs.length === 0 ? (
          <p className="text-small text-content-muted">{MISSING.none}</p>
        ) : (
          <ul className="list-disc space-y-1 pl-5 text-body text-content-secondary">
            {needs.map((need) => (
              <li key={need}>{need}</li>
            ))}
          </ul>
        )}
      </div>

      <div className="space-y-2">
        <h4 className="text-small font-medium text-content">Pain points</h4>
        <ClaimList items={pains} analysis="market" sources={sources} onOpenSource={onOpenSource} empty={MISSING.none} />
      </div>

      {isPriority && priority ? (
        <div className="space-y-3 border-t border-line pt-4">
          <h4 className="text-small font-medium text-content">Why this segment first</h4>
          <p className="max-w-prose text-body text-content-secondary">{priority.rationale}</p>
          {/* The rationale is the model's reading of the evidence, so it is labelled as such. */}
          <BasisChip basis="ai_interpretation" />
          {(priority.risks ?? []).length > 0 ? (
            <div className="space-y-1">
              <h4 className="text-small font-medium text-content">Risks</h4>
              <ul className="list-disc space-y-1 pl-5 text-body text-content-secondary">
                {(priority.risks ?? []).map((risk) => (
                  <li key={risk}>{risk}</li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      ) : null}
    </article>
  );
}

export interface MarketTabProps {
  result: PipelineResult;
  sources: Map<string, SourceRecord>;
  onOpenSource: (key: string) => void;
}

export function MarketTab({ result, sources, onOpenSource }: MarketTabProps) {
  const market = result.market;

  // Section 6.8: a stage that did not finish gets a panel saying which one and why.
  if (!market) {
    const reason = stageProblem(result, 'market_opportunity');
    return (
      <Alert tone="warning" title="Analysing the market did not finish">
        {reason ?? 'The market analysis did not run for this validation, so there is nothing to show here.'}
      </Alert>
    );
  }

  const overview = market.industry_overview;
  const demand = market.market_demand;
  const trends = market.trends ?? [];
  const broader = market.broader_markets ?? [];
  const notes = market.data_quality.notes ?? [];

  function jump(id: string): void {
    const target = document.getElementById(id);
    if (!target) {
      return;
    }
    const reduce = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false;
    target.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'start' });
    // Move focus with the view, so a keyboard user continues from the section they chose.
    document.getElementById(`${id}-heading`)?.focus({ preventScroll: true });
  }

  return (
    <div className="grid gap-8 lg:grid-cols-[13rem_minmax(0,1fr)]">
      {/*
        min-w-0 matters below lg, where this is the first row of a one-column grid: without it the
        column is sized to the section list's max-content width, about 620 px, which made the whole
        tab scroll sideways on a phone even though the list itself scrolls.
      */}
      <nav aria-label="Market sections" className="min-w-0 lg:sticky lg:top-6 lg:self-start">
        <ul className="flex gap-1 overflow-x-auto lg:flex-col">
          {SECTIONS.map((section) => (
            <li key={section.id} className="shrink-0">
              <a
                href={`#${section.id}`}
                onClick={(event) => {
                  event.preventDefault();
                  jump(section.id);
                }}
                className={cn(
                  'flex min-h-[44px] items-center rounded-control px-3 text-small text-content-secondary sm:min-h-9',
                  'transition-colors duration-tab hover:bg-raised hover:text-content',
                )}
              >
                {section.label}
              </a>
            </li>
          ))}
        </ul>
      </nav>

      <div className="min-w-0 space-y-12">
        <Section id="market-overview" title="Industry overview">
          <div className="space-y-4 rounded-panel border border-line bg-surface p-6">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-small text-content-muted">Market category</span>
              <span className="rounded-pill border border-line bg-raised px-3 py-0.5 text-small text-content">
                {overview.market_category}
              </span>
            </div>
            <p className="max-w-prose text-body text-content-secondary">{overview.summary}</p>
            {/* The summary is the model's own wording over the items below. */}
            <BasisChip basis="ai_interpretation" />
            <div className="space-y-2 border-t border-line pt-4">
              <h3>Developments</h3>
              <ClaimList
                items={overview.developments ?? []}
                analysis="market"
                sources={sources}
                onOpenSource={onOpenSource}
                empty={MISSING.none}
              />
            </div>
          </div>
        </Section>

        <Section id="market-demand" title="Demand">
          <div className="space-y-6 rounded-panel border border-line bg-surface p-6">
            <div className="space-y-2">
              <p className="max-w-prose text-body text-content-secondary">{demand.summary}</p>
              <BasisChip basis="ai_interpretation" />
            </div>
            <div className="grid gap-6 lg:grid-cols-3">
              {(
                [
                  ['Demand evidence', demand.demand_evidence ?? []],
                  ['Customer problems', demand.customer_problems ?? []],
                  ['Interest signals', demand.interest_signals ?? []],
                ] as const
              ).map(([title, items]) => (
                <div key={title} className="space-y-2">
                  <h3>{title}</h3>
                  <ClaimList
                    items={[...items]}
                    analysis="market"
                    sources={sources}
                    onOpenSource={onOpenSource}
                    empty={MISSING.none}
                  />
                </div>
              ))}
            </div>
          </div>
        </Section>

        <Section
          id="market-size"
          title="Market size"
          description="TAM, SAM and SOM for this idea's own market only. A figure appears only when a cited source states it."
        >
          <div className="grid gap-4 sm:grid-cols-3">
            {FIGURE_LABELS.map(([field, label]) => (
              <FigureTile
                key={field}
                label={label}
                figure={market.market_size[field]}
                sources={sources}
                onOpenSource={onOpenSource}
              />
            ))}
          </div>

          <div className="space-y-3 rounded-panel border border-line bg-surface p-6">
            <div className="space-y-1">
              <h3 id="broader-heading">Broader markets (context only)</h3>
              <p className="max-w-prose text-small text-content-muted">{MSG_BROADER}</p>
            </div>
            {broader.length === 0 ? (
              <p className="text-small text-content-muted">No broader-market figures were found.</p>
            ) : (
              // Section 6.4 rule 6: text left, figures right, and a scroll hint on a narrow screen.
              <div className="overflow-x-auto">
                <table aria-labelledby="broader-heading" className="w-full min-w-[32rem] text-small">
                  <thead>
                    <tr className="border-b border-line text-content-secondary">
                      <th scope="col" className="py-2 pr-4 text-left font-medium">
                        What it measures
                      </th>
                      <th scope="col" className="py-2 pr-4 text-right font-medium">
                        Figure
                      </th>
                      <th scope="col" className="py-2 pr-4 text-left font-medium">
                        Status
                      </th>
                      <th scope="col" className="py-2 text-left font-medium">
                        Sources
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {broader.map((figure, index) => (
                      <tr key={`${figure.value}-${index}`} className="border-b border-line align-top">
                        <td className="py-2 pr-4 text-content-secondary">{figure.note || MISSING.none}</td>
                        <th scope="row" className="tabular py-2 pr-4 text-right font-medium text-content">
                          {figure.value ?? MISSING.marketSize}
                        </th>
                        <td className="py-2 pr-4">
                          <StatusChip kind={figureStatus(figure)} />
                        </td>
                        <td className="py-2">
                          <Citations
                            sources={resolveSources(sources, 'market', figure.source_ids)}
                            onOpen={onOpenSource}
                          />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <p className="mt-2 text-micro text-content-muted sm:hidden">Scroll sideways to see every column.</p>
              </div>
            )}
          </div>
        </Section>

        <Section id="market-trends" title="Trends">
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {TREND_COLUMNS.map((column) => {
              const items = trends.filter((trend) => trend.category === column.key);
              return (
                <div key={column.key} className="space-y-3 rounded-panel border border-line bg-surface p-4">
                  <h3>{column.label}</h3>
                  {items.length === 0 ? (
                    <p className="text-small text-content-muted">{MSG_NO_TREND}</p>
                  ) : (
                    <ul className="space-y-4">
                      {items.map((trend, index) => (
                        <ClaimItem
                          key={`${column.key}-${index}`}
                          item={{ text: trend.trend, basis: trend.basis, source_ids: trend.source_ids ?? [] }}
                          analysis="market"
                          sources={sources}
                          onOpenSource={onOpenSource}
                        />
                      ))}
                    </ul>
                  )}
                </div>
              );
            })}
          </div>
        </Section>

        <Section id="market-segments" title="Segments">
          {market.priority_segment ? null : (
            <p className="max-w-prose text-small text-content-muted">
              No priority segment could be chosen from the segments found.
            </p>
          )}
          <div className="grid gap-4 lg:grid-cols-2">
            {(market.segments ?? []).map((segment) => (
              <SegmentCard
                key={segment.name}
                segment={segment}
                priority={market.priority_segment}
                sources={sources}
                onOpenSource={onOpenSource}
              />
            ))}
          </div>
        </Section>

        <Section id="market-opportunities" title="Opportunities and limitations">
          <div className="grid gap-4 lg:grid-cols-2">
            <div className="space-y-3 rounded-panel border border-line bg-surface p-6">
              <h3>Opportunities</h3>
              <ClaimList
                items={market.opportunities ?? []}
                analysis="market"
                sources={sources}
                onOpenSource={onOpenSource}
                empty={MISSING.none}
              />
            </div>
            <div className="space-y-3 rounded-panel border border-line bg-surface p-6">
              <h3>Limitations</h3>
              <ClaimList
                items={market.limitations ?? []}
                analysis="market"
                sources={sources}
                onOpenSource={onOpenSource}
                empty={MISSING.none}
              />
            </div>
          </div>
        </Section>

        <Section
          id="market-evidence"
          title="Evidence notes"
          description={`The market evidence was rated ${LEVEL_WORD[market.data_quality.evidence_level]}. These are the points it could not settle.`}
        >
          <div className="space-y-4 rounded-panel border border-line bg-surface p-6">
            {notes.length === 0 ? (
              <p className="text-small text-content-muted">The analysis recorded no open points.</p>
            ) : (
              <ul className="list-disc space-y-2 pl-5 text-body text-content-secondary">
                {notes.map((note) => (
                  <li key={note} className="max-w-prose">
                    <TextWithCitations text={note} analysis="market" sources={sources} onOpenSource={onOpenSource} />
                  </li>
                ))}
              </ul>
            )}
            {(market.caveats ?? []).map((caveat) => (
              <p key={caveat} className="border-t border-line pt-4 text-small text-content-muted">
                {caveat}
              </p>
            ))}
          </div>
        </Section>
      </div>
    </div>
  );
}
