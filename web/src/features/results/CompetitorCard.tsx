/**
 * Competitor card (KIRO_UI_UPGRADE_SPEC.md Sections 6.5, 6.8 and 7.4).
 *
 * The fields always come in the same order, so two cards can be read side by side: name, type,
 * website, offering, target, key features, pricing, strengths, weaknesses, sources. The less
 * important fields (value proposition, positioning, how the startup differs) are folded into the
 * collapsible details, as Section 6.5 asks of an entity card.
 *
 * Section 6.8 decides every empty value. A price is shown only when a cited source states it; a
 * price marked "sourced" with no figure is shown as not found, never as a blank sourced price.
 */

import { ChevronRight, ExternalLink } from 'lucide-react';
import * as React from 'react';

import type { components } from '@/api/types.gen';
import { BasisChip } from '@/components/BasisChip';
import { Citations } from '@/components/CitationChip';
import { ClaimList } from '@/components/Claim';
import { StatusChip } from '@/components/StatusChip';
import { cn } from '@/lib/cn';
import { MISSING, domainOf } from '@/lib/format';
import { type SourceRecord, resolveSources } from '@/lib/results';

export type Competitor = components['schemas']['Competitor'];
export type CompetitorType = Competitor['type'];

export const TYPE_LABEL: Record<CompetitorType, string> = {
  direct: 'Direct',
  indirect: 'Indirect',
  emerging: 'Emerging',
};

const COMPLETENESS: Record<Competitor['info_completeness'], string> = {
  complete: 'Detail found',
  partial: 'Some detail found',
  minimal: 'Little detail found',
};

/** Section 6.8: a website the sources did not confirm is a dash with a tooltip. */
function Website({ url }: { url: string | null | undefined }) {
  const domain = domainOf(url);
  if (!url || !domain) {
    return (
      <span title={MISSING.websiteHint} className="text-content-muted">
        {MISSING.website}
        <span className="sr-only"> {MISSING.websiteHint}</span>
      </span>
    );
  }
  return (
    <a
      href={url}
      target="_blank"
      rel="noreferrer noopener"
      className="inline-flex min-h-[44px] items-center gap-1 font-mono text-small text-primary underline underline-offset-2 hover:text-primary-hover sm:min-h-0"
    >
      {domain}
      <ExternalLink className="size-3.5" aria-hidden="true" />
      <span className="sr-only">(opens in a new tab)</span>
    </a>
  );
}

/** Only a price with a value counts. A sourced status with no figure is treated as not found. */
function Pricing({
  price,
  sources,
  onOpenSource,
}: {
  price: Competitor['pricing_model'];
  sources: Map<string, SourceRecord>;
  onOpenSource: (key: string) => void;
}) {
  const value = price?.value?.trim();
  if (!price || !value || price.status === 'unavailable') {
    return <span className="text-content-muted">{MISSING.price}</span>;
  }
  return (
    <span className="inline-flex flex-wrap items-center gap-2">
      <span className="text-content">{value}</span>
      {price.status === 'estimate_needs_verification' ? <StatusChip kind="estimate" /> : null}
      <Citations sources={resolveSources(sources, 'competitors', price.source_ids)} onOpen={onOpenSource} />
    </span>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid gap-1 sm:grid-cols-[9rem_minmax(0,1fr)] sm:gap-4">
      <dt className="text-small text-content-muted">{label}</dt>
      <dd className="min-w-0 text-body text-content-secondary">{children}</dd>
    </div>
  );
}

export interface CompetitorCardProps {
  competitor: Competitor;
  sources: Map<string, SourceRecord>;
  onOpenSource: (key: string) => void;
}

export function CompetitorCard({ competitor, sources, onOpenSource }: CompetitorCardProps) {
  // A name can hold spaces, so the heading gets an id React generates (see the segment cards).
  const headingId = React.useId();
  const features = competitor.key_features ?? [];
  const cited = resolveSources(sources, 'competitors', competitor.source_ids);
  const extras = [
    ['Value proposition', competitor.value_proposition],
    ['Positioning', competitor.positioning],
    ['How your idea differs', competitor.differentiation_vs_startup],
    ['Why it is listed', competitor.relevance_note],
  ].filter((entry): entry is [string, string] => Boolean(entry[1]?.trim()));

  return (
    <article aria-labelledby={headingId} className="flex flex-col gap-4 rounded-panel border border-line bg-surface p-6">
      {/* Section 6.4 rule 4: title left, meta right. */}
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h3 id={headingId} className="break-words">
          {competitor.name}
        </h3>
        <div className="flex flex-wrap items-center gap-2">
          <span className="rounded-pill border border-line bg-raised px-3 py-0.5 text-micro text-content">
            {TYPE_LABEL[competitor.type]}
          </span>
          {competitor.basis === 'user_provided' ? <BasisChip basis="user_provided" /> : null}
        </div>
      </div>

      <dl className="space-y-3">
        <Row label="Website">
          <Website url={competitor.website} />
        </Row>
        <Row label="Offering">
          {competitor.offering?.trim() || <span className="text-content-muted">{MISSING.none}</span>}
        </Row>
        <Row label="Target">
          {competitor.target_segment?.trim() || <span className="text-content-muted">{MISSING.none}</span>}
        </Row>
        <Row label="Key features">
          {features.length === 0 ? (
            <span className="text-content-muted">{MISSING.none}</span>
          ) : (
            <ul className="flex flex-wrap gap-2">
              {features.map((feature) => (
                <li
                  key={feature}
                  className="rounded-pill border border-line bg-raised px-3 py-0.5 text-micro text-content"
                >
                  {feature}
                </li>
              ))}
            </ul>
          )}
        </Row>
        <Row label="Pricing">
          <Pricing price={competitor.pricing_model} sources={sources} onOpenSource={onOpenSource} />
        </Row>
      </dl>

      <div className="space-y-2 border-t border-line pt-4">
        <h4 className="text-small font-medium text-content">Strengths</h4>
        <ClaimList
          items={competitor.strengths ?? []}
          analysis="competitors"
          sources={sources}
          onOpenSource={onOpenSource}
          empty="None found in the sources."
        />
      </div>

      <div className="space-y-2">
        <h4 className="text-small font-medium text-content">Weaknesses</h4>
        <ClaimList
          items={competitor.weaknesses ?? []}
          analysis="competitors"
          sources={sources}
          onOpenSource={onOpenSource}
          empty={MISSING.weaknesses}
        />
      </div>

      <div className="flex flex-wrap items-center gap-2 border-t border-line pt-4">
        <span className="text-small text-content-muted">Sources</span>
        {competitor.basis === 'user_provided' && cited.length === 0 ? (
          <span className="text-small text-content-muted">Named in your submission</span>
        ) : cited.length === 0 ? (
          <span className="text-small text-content-muted">{MISSING.none}</span>
        ) : (
          <Citations sources={cited} onOpen={onOpenSource} />
        )}
        <span className="ml-auto text-micro text-content-muted">{COMPLETENESS[competitor.info_completeness]}</span>
      </div>

      {extras.length > 0 ? (
        <details className="group">
          <summary className="flex min-h-[44px] cursor-pointer items-center gap-2 text-small text-content sm:min-h-0">
            <ChevronRight
              className="size-4 transition-transform duration-tab group-open:rotate-90"
              aria-hidden="true"
            />
            More about {competitor.name}
          </summary>
          <dl className={cn('mt-3 space-y-3')}>
            {extras.map(([label, text]) => (
              <Row key={label} label={label}>
                {text}
              </Row>
            ))}
          </dl>
          {/* These are the model's own descriptions, so they are labelled as interpretation. */}
          <div className="mt-3">
            <BasisChip basis="ai_interpretation" />
          </div>
        </details>
      ) : null}
    </article>
  );
}
