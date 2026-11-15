import { AlertTriangle, CheckCircle2, ChevronRight, Clock, User } from 'lucide-react';
import * as React from 'react';

import type { components } from '@/api/types.gen';
import { BasisChip } from '@/components/BasisChip';
import { Chip } from '@/components/Chip';
import { Citations } from '@/components/CitationChip';
import { cn } from '@/lib/cn';
import { count } from '@/lib/format';
import { resolveStrategySources, type PipelineResult, type SourceRecord } from '@/lib/results';

type Mvp = NonNullable<PipelineResult['mvp']>;
type Swot = NonNullable<PipelineResult['swot']>;
type Feature = components['schemas']['MvpFeature'];
type Metric = components['schemas']['MvpMetric'];
type Tier = Feature['tier'];

export const SCORE_WEIGHTS = { need: 0.4, differentiation: 0.3, feasibility: 0.3 } as const;
export const EFFORT_MONTHS = { S: 0.5, M: 1, L: 2 } as const;
export const FOCUS_FACTOR = 0.6;
const DEFAULT_TEAM = 2;
const DEFAULT_MONTHS = 3;

export const MVP_COPY = {
  firstRelease: 'In the first release',
  later: 'Later',
  overCapacity: 'Over capacity',
  overCapacityNote:
    'The essential features need more effort than your team and time allow. Narrow the idea or allow more time.',
  noRisks: 'Risks were not considered when choosing features.',
  ranking: 'How the ranking works',
  noFeatures: 'No features in this list.',
  noMetrics: 'No success metrics were given.',
} as const;

const TIER: Record<Tier, { label: string; Icon: typeof CheckCircle2; className: string }> = {
  mvp: { label: 'First release', Icon: CheckCircle2, className: 'bg-success-bg text-success border-success-border' },
  later: { label: 'Later', Icon: Clock, className: 'bg-info-bg text-info border-info-border' },
};

function amount(value: number): string {
  return String(Number(value.toFixed(2)));
}

export function capacityLine(mvp: Mvp): string {
  return `Planned ${amount(mvp.planned_person_months)} of ${amount(mvp.capacity_person_months)} person-months`;
}

function resources(mvp: Mvp): { team: number; months: number } {
  const used = mvp.constraints_used;
  return { team: used.team_size ?? DEFAULT_TEAM, months: used.months_to_mvp ?? DEFAULT_MONTHS };
}

export function assumptionsLine(mvp: Mvp): string {
  const { team, months } = resources(mvp);
  return `Based on a team of ${team} and ${count(months, 'month')} to the first release.`;
}

export function mvpAssumedChips(mvp: Mvp): string[] {
  const assumed = mvp.quality?.constraints_assumed ?? [];
  const { team, months } = resources(mvp);
  const chips: string[] = [];
  if (assumed.includes('team_size')) {
    chips.push(`Assumed: team of ${team}`);
  }
  if (assumed.includes('months_to_mvp')) {
    chips.push(`Assumed: ${count(months, 'month')}`);
  }
  return chips;
}

export function linkedRiskTitles(feature: Feature, swot: Swot | null): string[] {
  const risks = swot?.risks ?? [];
  const titles: string[] = [];
  for (const id of feature.mitigates_risk_ids ?? []) {
    const risk = risks.find((entry) => entry.id.trim().toUpperCase() === id.trim().toUpperCase());
    if (risk && !titles.includes(risk.title)) {
      titles.push(risk.title);
    }
  }
  return titles;
}

export function originLabel(origin: Feature['origin']): string {
  return origin === 'founder_listed' ? 'Your feature' : 'Suggested';
}

function TierChip({ tier }: { tier: Tier }) {
  const { label, Icon, className } = TIER[tier];
  return (
    <span className={cn('inline-flex h-6 items-center gap-2 rounded-pill border px-3 text-micro', className)}>
      <Icon className="size-3.5 shrink-0" aria-hidden="true" />
      {label}
    </span>
  );
}

function Rating({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex items-baseline gap-2">
      <dt className="text-small text-content-muted">{label}</dt>
      <dd className="tabular text-small text-content">{value} of 5</dd>
    </div>
  );
}

function FeatureCard({
  feature,
  swot,
  deferred,
  sources,
  onOpenSource,
}: {
  feature: Feature;
  swot: Swot | null;
  deferred: string | undefined;
  sources: Map<string, SourceRecord>;
  onOpenSource: (key: string) => void;
}) {
  const headingId = React.useId();
  const risks = linkedRiskTitles(feature, swot);
  return (
    <article aria-labelledby={headingId} className="flex min-w-0 flex-col gap-4 rounded-panel border border-line bg-surface p-6">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <div className="flex min-w-0 items-baseline gap-3">
          <span className="tabular shrink-0 text-small text-content-muted">Rank {feature.rank}</span>
          <h4 id={headingId} className="break-words text-body font-medium text-content">
            {feature.name}
          </h4>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <TierChip tier={feature.tier} />
          <Chip>Effort: {feature.effort}, AI estimate</Chip>
          <Chip>
            {feature.origin === 'founder_listed' ? (
              <User className="size-3.5 shrink-0" aria-hidden="true" />
            ) : null}
            {originLabel(feature.origin)}
          </Chip>
        </div>
      </div>

      <dl className="flex flex-wrap gap-x-6 gap-y-2">
        <div className="flex items-baseline gap-2">
          <dt className="text-small text-content-muted">Score</dt>
          <dd className="tabular text-small font-medium text-content">{feature.score.toFixed(2)} of 5</dd>
        </div>
        <Rating label="Need" value={feature.customer_need} />
        <Rating label="Differentiation" value={feature.differentiation} />
        <Rating label="Feasibility" value={feature.feasibility} />
      </dl>

      {feature.rationale ? (
        <p className="max-w-prose text-body text-content-secondary">
          {feature.rationale}{' '}
          <Citations sources={resolveStrategySources(sources, feature.sources)} onOpen={onOpenSource} />
        </p>
      ) : (
        <Citations sources={resolveStrategySources(sources, feature.sources)} onOpen={onOpenSource} />
      )}

      {deferred ? (
        <p className="max-w-prose text-small text-content-muted">
          <span className="text-content-secondary">Why later: </span>
          {deferred}
        </p>
      ) : null}

      {risks.length > 0 ? (
        <div className="space-y-1">
          <p className="text-small text-content-muted">Reduces these risks</p>
          <ul className="flex flex-wrap gap-2">
            {risks.map((title) => (
              <li key={title}>
                <Chip>{title}</Chip>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <div>
        <BasisChip basis={feature.basis} />
      </div>
    </article>
  );
}

function FeatureList({
  title,
  features,
  mvp,
  swot,
  sources,
  onOpenSource,
}: {
  title: string;
  features: Feature[];
  mvp: Mvp;
  swot: Swot | null;
  sources: Map<string, SourceRecord>;
  onOpenSource: (key: string) => void;
}) {
  const headingId = React.useId();
  return (
    <section aria-labelledby={headingId} className="space-y-4">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h3 id={headingId}>{title}</h3>
        <span className="tabular text-small text-content-muted">{count(features.length, 'feature')}</span>
      </div>
      {features.length === 0 ? (
        <p className="max-w-prose text-small text-content-muted">{MVP_COPY.noFeatures}</p>
      ) : (
        <ul aria-labelledby={headingId} className="grid gap-4 xl:grid-cols-2">
          {features.map((feature) => (
            <li key={feature.id} className="min-w-0">
              <FeatureCard
                feature={feature}
                swot={swot}
                deferred={feature.tier === 'later' ? mvp.deferred_reasons?.[feature.id] : undefined}
                sources={sources}
                onOpenSource={onOpenSource}
              />
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function MetricItem({ metric }: { metric: Metric }) {
  return (
    <li className="space-y-2">
      <p className="text-body font-medium text-content">{metric.name}</p>
      <p className="max-w-prose text-body text-content-secondary">{metric.how_to_measure}</p>
      {metric.suggested_target ? (
        <p className="max-w-prose text-small text-content-muted">
          <span className="text-content-secondary">Suggested target, an assumption: </span>
          {metric.suggested_target}
        </p>
      ) : null}
      <BasisChip basis={metric.basis} />
    </li>
  );
}

export interface MvpSectionProps {
  mvp: Mvp;
  swot: Swot | null;
  sources: Map<string, SourceRecord>;
  onOpenSource: (key: string) => void;
}

export function MvpSection({ mvp, swot, sources, onOpenSource }: MvpSectionProps) {
  const features = mvp.features ?? [];
  const first = features.filter((feature) => feature.tier === 'mvp');
  const later = features.filter((feature) => feature.tier === 'later');
  const metrics = mvp.success_metrics ?? [];
  const chips = mvpAssumedChips(mvp);
  const share = mvp.capacity_person_months > 0 ? Math.min(mvp.planned_person_months / mvp.capacity_person_months, 1) : 1;
  const noRisks = !swot || (mvp.quality?.inputs_missing ?? []).includes('swot');

  return (
    <div className="space-y-8">
      <div className="space-y-3 rounded-panel border border-line bg-surface p-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="tabular text-body text-content">{capacityLine(mvp)}</p>
          {mvp.over_capacity ? (
            <span className="inline-flex h-6 items-center gap-2 rounded-pill border border-warning-border bg-warning-bg px-3 text-micro text-warning">
              <AlertTriangle className="size-3.5 shrink-0" aria-hidden="true" />
              {MVP_COPY.overCapacity}
            </span>
          ) : null}
        </div>
        <div aria-hidden="true" className="h-2 w-full overflow-hidden rounded-pill bg-raised">
          <div
            className={cn('h-full rounded-pill', mvp.over_capacity ? 'bg-warning' : 'bg-primary')}
            style={{ width: `${share * 100}%` }}
          />
        </div>
        {mvp.over_capacity ? (
          <p className="max-w-prose text-small text-content-secondary">{MVP_COPY.overCapacityNote}</p>
        ) : null}
        <p className="max-w-prose text-small text-content-muted">{assumptionsLine(mvp)}</p>
        {chips.length > 0 ? (
          <ul aria-label="Assumed resources" className="flex flex-wrap gap-2">
            {chips.map((chip) => (
              <li key={chip}>
                <Chip>{chip}</Chip>
              </li>
            ))}
          </ul>
        ) : null}
        {noRisks ? <p className="max-w-prose text-small text-content-muted">{MVP_COPY.noRisks}</p> : null}
      </div>

      <FeatureList
        title={MVP_COPY.firstRelease}
        features={first}
        mvp={mvp}
        swot={swot}
        sources={sources}
        onOpenSource={onOpenSource}
      />
      <FeatureList
        title={MVP_COPY.later}
        features={later}
        mvp={mvp}
        swot={swot}
        sources={sources}
        onOpenSource={onOpenSource}
      />

      <details className="group rounded-panel border border-line bg-surface p-6">
        <summary className="flex min-h-[44px] cursor-pointer items-center gap-2 text-body text-content sm:min-h-0">
          <ChevronRight className="size-4 transition-transform duration-tab group-open:rotate-90" aria-hidden="true" />
          {MVP_COPY.ranking}
        </summary>
        <div className="mt-4 max-w-prose space-y-2 text-small text-content-secondary">
          <p>
            Each feature is rated from 1 to 5 by the AI for need, differentiation and feasibility. Score ={' '}
            {SCORE_WEIGHTS.need} × need + {SCORE_WEIGHTS.differentiation} × differentiation +{' '}
            {SCORE_WEIGHTS.feasibility} × feasibility.
          </p>
          <p>Features essential to the idea come first, then higher scores, then lower effort.</p>
          <p>
            Effort in person-months, an AI estimate: S is {EFFORT_MONTHS.S}, M is {EFFORT_MONTHS.M}, L is{' '}
            {EFFORT_MONTHS.L}.
          </p>
          <p>
            Capacity = team size × months × {FOCUS_FACTOR}, for the time a team can give to building. Features join
            the first release in rank order while they fit.
          </p>
          <p className="text-content-muted">These weights are planning rules of thumb, not facts about your market.</p>
        </div>
      </details>

      <section aria-labelledby="mvp-metrics-heading" className="space-y-4 rounded-panel border border-line bg-surface p-6">
        <h3 id="mvp-metrics-heading">Success metrics</h3>
        {metrics.length === 0 ? (
          <p className="max-w-prose text-small text-content-muted">{MVP_COPY.noMetrics}</p>
        ) : (
          <ul className="space-y-4">
            {metrics.map((metric, index) => (
              <MetricItem key={`${metric.name}-${index}`} metric={metric} />
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
