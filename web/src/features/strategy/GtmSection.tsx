import { AlertTriangle, CheckCircle2, Flag, FlaskConical } from 'lucide-react';
import * as React from 'react';

import type { components } from '@/api/types.gen';
import { BasisChip } from '@/components/BasisChip';
import { Chip } from '@/components/Chip';
import { Citations } from '@/components/CitationChip';
import { cn } from '@/lib/cn';
import { count } from '@/lib/format';
import { resolveStrategySources, type PipelineResult, type SourceRecord } from '@/lib/results';

type Gtm = NonNullable<PipelineResult['gtm']>;
type Mvp = NonNullable<PipelineResult['mvp']>;
type Swot = NonNullable<PipelineResult['swot']>;
type Positioning = components['schemas']['Positioning'];
type Channel = components['schemas']['Channel'];
type Tactic = components['schemas']['EarlyCustomerTactic'];
type Phase = components['schemas']['LaunchPhase'];

export const GTM_COPY = {
  startHere: 'Start here',
  budgetConflict: 'May be above a bootstrapped budget',
  hypothesis: 'Hypothesis',
  supported: 'Supported',
  noRisks: 'Risks were not considered when planning go-to-market.',
  noFeatures: 'The plan is not tied to a feature set because no MVP recommendation was available.',
  notGiven: 'Not given',
  noneReturned: 'None were returned.',
} as const;

export const KIND_WORD: Record<Channel['kind'], string> = {
  digital: 'Digital',
  community: 'Community',
  partnership: 'Partnership',
  offline: 'Offline',
  direct_sales: 'Direct sales',
  product_led: 'Product-led',
};

export const ROLE_WORD: Record<Channel['role'], string> = {
  acquisition: 'Acquisition',
  distribution: 'Distribution',
  both: 'Acquisition and distribution',
};

export const COST_WORD: Record<Channel['cost_level'], string> = { low: 'Low', medium: 'Medium', high: 'High' };

export const SPEED_WORD: Record<Channel['speed_to_first_result'], string> = {
  days: 'Days',
  weeks: 'Weeks',
  months: 'Months',
};

export const FIT_WORD: Record<number, string> = {
  1: 'Very weak',
  2: 'Weak',
  3: 'Moderate',
  4: 'Strong',
  5: 'Very strong',
};

const METER_STEPS = [1, 2, 3, 4, 5] as const;

type PartKey = 'for_whom' | 'problem' | 'category' | 'key_benefit' | 'alternative';

const PARTS: { key: PartKey; label: string }[] = [
  { key: 'for_whom', label: 'For whom' },
  { key: 'problem', label: 'Problem' },
  { key: 'category', label: 'Category' },
  { key: 'key_benefit', label: 'Key benefit' },
  { key: 'alternative', label: 'Alternative' },
];

function fitStep(value: number): number {
  return Math.min(5, Math.max(1, Math.round(value)));
}

export function fitText(value: number): string {
  const step = fitStep(value);
  return `${FIT_WORD[step]}, ${step} of 5`;
}

function sameId(a: string, b: string): boolean {
  return a.trim().toUpperCase() === b.trim().toUpperCase();
}

export function linkedFeatureNames(channel: Channel, mvp: Mvp | null): string[] {
  const features = mvp?.features ?? [];
  const names: string[] = [];
  for (const id of channel.uses_feature_ids ?? []) {
    const feature = features.find((entry) => sameId(entry.id, id));
    if (feature && !names.includes(feature.name)) {
      names.push(feature.name);
    }
  }
  return names;
}

export function linkedRiskNames(channel: Channel, swot: Swot | null): string[] {
  const risks = swot?.risks ?? [];
  const titles: string[] = [];
  for (const id of channel.addresses_risk_ids ?? []) {
    const risk = risks.find((entry) => sameId(entry.id, id));
    if (risk && !titles.includes(risk.title)) {
      titles.push(risk.title);
    }
  }
  return titles;
}

function DifferentiatorChip({ supported }: { supported: boolean }) {
  const Icon = supported ? CheckCircle2 : FlaskConical;
  return (
    <span
      className={cn(
        'inline-flex h-6 items-center gap-2 rounded-pill border px-3 text-micro',
        supported ? 'border-success-border bg-success-bg text-success' : 'border-info-border bg-info-bg text-info',
      )}
    >
      <Icon className="size-3.5 shrink-0" aria-hidden="true" />
      {supported ? GTM_COPY.supported : GTM_COPY.hypothesis}
    </span>
  );
}

function SubSection({ title, children }: { title: string; children: React.ReactNode }) {
  const headingId = React.useId();
  return (
    <section aria-labelledby={headingId} className="space-y-4">
      <h3 id={headingId}>{title}</h3>
      {children}
    </section>
  );
}

function PositioningCard({
  positioning,
  sources,
  onOpenSource,
}: {
  positioning: Positioning;
  sources: Map<string, SourceRecord>;
  onOpenSource: (key: string) => void;
}) {
  return (
    <div className="space-y-4 rounded-panel border border-line bg-surface p-6">
      <p className="text-small text-content-muted">
        Target segment: <span className="text-content">{positioning.target_segment}</span>
      </p>
      <p className="max-w-prose text-body text-content">
        {positioning.statement}{' '}
        <Citations sources={resolveStrategySources(sources, positioning.sources)} onOpen={onOpenSource} />
      </p>
      <dl className="grid gap-2 text-small sm:grid-cols-[max-content_minmax(0,1fr)] sm:gap-x-4">
        {PARTS.map((part) => (
          <React.Fragment key={part.key}>
            <dt className="text-content-muted">{part.label}</dt>
            <dd className="text-content-secondary">{positioning[part.key]}</dd>
          </React.Fragment>
        ))}
        <dt className="text-content-muted">Differentiator</dt>
        <dd className="flex flex-wrap items-center gap-2 text-content-secondary">
          <span>{positioning.differentiator}</span>
          <DifferentiatorChip supported={positioning.differentiator_status === 'supported'} />
        </dd>
      </dl>
      <BasisChip basis={positioning.basis} />
    </div>
  );
}

function FitMeter({ value }: { value: number }) {
  const step = fitStep(value);
  return (
    <span className="flex flex-wrap items-center gap-3">
      <span aria-hidden="true" className="flex gap-1">
        {METER_STEPS.map((entry) => (
          <span
            key={entry}
            className={cn('h-2 w-5 rounded-pill', entry <= step ? 'bg-primary' : 'bg-raised')}
          />
        ))}
      </span>
      <span className="tabular">{fitText(value)}</span>
    </span>
  );
}

function NamedChips({ label, names }: { label: string; names: string[] }) {
  if (names.length === 0) {
    return null;
  }
  return (
    <div className="space-y-1">
      <p className="text-small text-content-muted">{label}</p>
      <ul aria-label={label} className="flex flex-wrap gap-2">
        {names.map((name) => (
          <li key={name}>
            <Chip>{name}</Chip>
          </li>
        ))}
      </ul>
    </div>
  );
}

function ChannelCard({
  channel,
  startHere,
  mvp,
  swot,
  sources,
  onOpenSource,
}: {
  channel: Channel;
  startHere: boolean;
  mvp: Mvp | null;
  swot: Swot | null;
  sources: Map<string, SourceRecord>;
  onOpenSource: (key: string) => void;
}) {
  const headingId = React.useId();
  return (
    <article aria-labelledby={headingId} className="flex min-w-0 flex-col gap-4 rounded-panel border border-line bg-surface p-6">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h4 id={headingId} className="break-words text-body font-medium text-content">
          {channel.name}
        </h4>
        <div className="flex flex-wrap items-center gap-2">
          {startHere ? (
            <span className="inline-flex h-6 items-center gap-2 rounded-pill border border-success-border bg-success-bg px-3 text-micro text-success">
              <Flag className="size-3.5 shrink-0" aria-hidden="true" />
              {GTM_COPY.startHere}
            </span>
          ) : null}
          {channel.budget_conflict ? (
            <span className="inline-flex h-6 items-center gap-2 rounded-pill border border-warning-border bg-warning-bg px-3 text-micro text-warning">
              <AlertTriangle className="size-3.5 shrink-0" aria-hidden="true" />
              {GTM_COPY.budgetConflict}
            </span>
          ) : null}
        </div>
      </div>

      {channel.fit_rationale ? (
        <p className="max-w-prose text-body text-content-secondary">
          {channel.fit_rationale}{' '}
          <Citations sources={resolveStrategySources(sources, channel.sources)} onOpen={onOpenSource} />
        </p>
      ) : (
        <Citations sources={resolveStrategySources(sources, channel.sources)} onOpen={onOpenSource} />
      )}

      <dl className="grid gap-2 text-small sm:grid-cols-[max-content_minmax(0,1fr)] sm:gap-x-4">
        <dt className="text-content-muted">Type</dt>
        <dd className="text-content-secondary">{KIND_WORD[channel.kind]}</dd>
        <dt className="text-content-muted">Role</dt>
        <dd className="text-content-secondary">{ROLE_WORD[channel.role]}</dd>
        <dt className="text-content-muted">Audience fit</dt>
        <dd className="text-content-secondary">
          <FitMeter value={channel.audience_fit} />
        </dd>
        <dt className="text-content-muted">Cost</dt>
        <dd className="text-content-secondary">{COST_WORD[channel.cost_level]}</dd>
        <dt className="text-content-muted">First results in</dt>
        <dd className="text-content-secondary">{SPEED_WORD[channel.speed_to_first_result]}</dd>
        <dt className="text-content-muted">First experiment</dt>
        <dd className="text-content-secondary">{channel.first_experiment}</dd>
        <dt className="text-content-muted">Success signal</dt>
        <dd className="text-content-secondary">{channel.success_signal}</dd>
      </dl>

      <NamedChips label="Uses these features" names={linkedFeatureNames(channel, mvp)} />
      <NamedChips label="Addresses these risks" names={linkedRiskNames(channel, swot)} />

      <div>
        <BasisChip basis={channel.basis} />
      </div>
    </article>
  );
}

function TacticCard({
  tactic,
  sources,
  onOpenSource,
}: {
  tactic: Tactic;
  sources: Map<string, SourceRecord>;
  onOpenSource: (key: string) => void;
}) {
  const headingId = React.useId();
  return (
    <article aria-labelledby={headingId} className="flex min-w-0 flex-col gap-3 rounded-panel border border-line bg-surface p-6">
      <h4 id={headingId} className="break-words text-body font-medium text-content">
        {tactic.tactic}
      </h4>
      <dl className="grid gap-2 text-small sm:grid-cols-[max-content_minmax(0,1fr)] sm:gap-x-4">
        <dt className="text-content-muted">Where to find them</dt>
        <dd className="text-content-secondary">{tactic.where_to_find_them}</dd>
        <dt className="text-content-muted">Offer</dt>
        <dd className="text-content-secondary">{tactic.offer}</dd>
        <dt className="text-content-muted">How to measure</dt>
        <dd className="text-content-secondary">{tactic.how_to_measure}</dd>
      </dl>
      <div className="flex flex-wrap items-center gap-2">
        <BasisChip basis={tactic.basis} />
        <Citations sources={resolveStrategySources(sources, tactic.sources)} onOpen={onOpenSource} />
      </div>
    </article>
  );
}

function PhaseItem({ phase }: { phase: Phase }) {
  const actions = phase.actions ?? [];
  return (
    <li className="space-y-2 pl-1">
      <h4 className="text-body font-medium text-content">{phase.name}</h4>
      <p className="max-w-prose text-body text-content-secondary">
        <span className="text-content-muted">Goal: </span>
        {phase.goal}
      </p>
      {actions.length > 0 ? (
        <ul className="list-disc space-y-1 pl-5 text-body text-content-secondary">
          {actions.map((action, index) => (
            <li key={`${action}-${index}`}>{action}</li>
          ))}
        </ul>
      ) : null}
    </li>
  );
}

export interface GtmSectionProps {
  gtm: Gtm;
  mvp: Mvp | null;
  swot: Swot | null;
  sources: Map<string, SourceRecord>;
  onOpenSource: (key: string) => void;
}

export function GtmSection({ gtm, mvp, swot, sources, onOpenSource }: GtmSectionProps) {
  const channels = gtm.channels ?? [];
  const tactics = gtm.early_customers ?? [];
  const phases = gtm.launch_phases ?? [];
  const messages = gtm.key_messages ?? [];
  const startIndex = channels.findIndex((channel) => channel.start_here);
  const missing = gtm.quality?.inputs_missing ?? [];
  const notes = [
    ...(!swot || missing.includes('swot') ? [GTM_COPY.noRisks] : []),
    ...(!mvp || missing.includes('mvp') ? [GTM_COPY.noFeatures] : []),
  ];

  return (
    <div className="space-y-8">
      {notes.length > 0 ? (
        <div className="space-y-1 rounded-panel border border-line bg-surface p-4">
          {notes.map((note) => (
            <p key={note} className="max-w-prose text-small text-content-muted">
              {note}
            </p>
          ))}
        </div>
      ) : null}

      <SubSection title="Positioning">
        <PositioningCard positioning={gtm.positioning} sources={sources} onOpenSource={onOpenSource} />
      </SubSection>

      <SubSection title="Channels">
        <p className="text-small text-content-muted">{count(channels.length, 'channel')}, best fit first</p>
        {channels.length === 0 ? (
          <p className="max-w-prose text-small text-content-muted">{GTM_COPY.noneReturned}</p>
        ) : (
          <ul aria-label="Channels" className="grid gap-4 xl:grid-cols-2">
            {channels.map((channel, index) => (
              <li key={`${channel.id}-${index}`} className="min-w-0">
                <ChannelCard
                  channel={channel}
                  startHere={index === startIndex}
                  mvp={mvp}
                  swot={swot}
                  sources={sources}
                  onOpenSource={onOpenSource}
                />
              </li>
            ))}
          </ul>
        )}
      </SubSection>

      <SubSection title="Early customers">
        {tactics.length === 0 ? (
          <p className="max-w-prose text-small text-content-muted">{GTM_COPY.noneReturned}</p>
        ) : (
          <ul aria-label="Early customers" className="grid gap-4 xl:grid-cols-2">
            {tactics.map((tactic, index) => (
              <li key={`${tactic.tactic}-${index}`} className="min-w-0">
                <TacticCard tactic={tactic} sources={sources} onOpenSource={onOpenSource} />
              </li>
            ))}
          </ul>
        )}
      </SubSection>

      <SubSection title="Launch plan">
        {phases.length === 0 ? (
          <p className="max-w-prose text-small text-content-muted">{GTM_COPY.noneReturned}</p>
        ) : (
          <ol
            aria-label="Launch plan"
            className="list-decimal space-y-6 rounded-panel border border-line bg-surface py-6 pl-10 pr-6 marker:text-content-muted"
          >
            {phases.map((phase, index) => (
              <PhaseItem key={`${phase.name}-${index}`} phase={phase} />
            ))}
          </ol>
        )}
      </SubSection>

      <SubSection title="Key messages">
        {messages.length === 0 ? (
          <p className="max-w-prose text-small text-content-muted">{GTM_COPY.noneReturned}</p>
        ) : (
          <div className="overflow-x-auto rounded-panel border border-line bg-surface">
            <table className="w-full text-small">
              <caption className="sr-only">Key messages, by audience.</caption>
              <thead>
                <tr className="border-b border-line text-content-secondary">
                  {['Audience', 'Message', 'Proof needed'].map((column) => (
                    <th key={column} scope="col" className="px-4 py-3 text-left font-medium">
                      {column}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {messages.map((message, index) => (
                  <tr key={`${message.audience}-${index}`} className="border-b border-line align-top last:border-b-0">
                    <th scope="row" className="px-4 py-3 text-left font-medium text-content">
                      {message.audience}
                    </th>
                    <td className="px-4 py-3 text-content-secondary">{message.message}</td>
                    <td className="px-4 py-3 text-content-secondary">
                      {message.proof_needed || <span className="text-content-muted">{GTM_COPY.notGiven}</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </SubSection>
    </div>
  );
}
