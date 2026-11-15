import { AlertTriangle, ChevronDown, CircleDashed, Info, ShieldAlert } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import * as React from 'react';

import type { components } from '@/api/types.gen';
import { BasisChip } from '@/components/BasisChip';
import { Citations } from '@/components/CitationChip';
import { controlClassName } from '@/components/Field';
import { NONE_FOUND } from '@/features/strategy/SwotSection';
import { cn } from '@/lib/cn';
import { count } from '@/lib/format';
import { resolveStrategySources, type PipelineResult, type SourceRecord } from '@/lib/results';
import { NARROW, useMediaQuery } from '@/lib/useMediaQuery';

type Swot = NonNullable<PipelineResult['swot']>;
type Risk = components['schemas']['RiskItem'];
type Level = Risk['severity'];
type Category = Risk['category'];

export const CATEGORIES: { key: Category; label: string }[] = [
  { key: 'business', label: 'Business' },
  { key: 'market', label: 'Market' },
  { key: 'technical', label: 'Technical' },
  { key: 'financial', label: 'Financial' },
  { key: 'operational', label: 'Operational' },
];

const CATEGORY_LABEL = Object.fromEntries(CATEGORIES.map((entry) => [entry.key, entry.label])) as Record<
  Category,
  string
>;

const LEVEL_WORD: Record<Level, string> = { high: 'High', medium: 'Medium', low: 'Low' };

const SEVERITY: Record<Level, { Icon: LucideIcon; className: string }> = {
  high: { Icon: ShieldAlert, className: 'bg-danger-bg text-danger border-danger-border' },
  medium: { Icon: AlertTriangle, className: 'bg-warning-bg text-warning border-warning-border' },
  low: { Icon: Info, className: 'bg-info-bg text-info border-info-border' },
};

export const GAP_NOTE = 'None found in this run. Not checked is not the same as safe.';

export type RiskSort = 'severity' | 'category';

export function sortRisks(risks: Risk[], sort: RiskSort): Risk[] {
  if (sort === 'severity') {
    return [...risks];
  }
  const order = CATEGORIES.map((entry) => entry.key);
  return risks
    .map((risk, index) => ({ risk, index }))
    .sort((a, b) => order.indexOf(a.risk.category) - order.indexOf(b.risk.category) || a.index - b.index)
    .map((entry) => entry.risk);
}

function words(labels: string[]): string {
  if (labels.length <= 1) {
    return labels.join('');
  }
  return `${labels.slice(0, -1).join(', ')} and ${labels[labels.length - 1]}`;
}

export function SeverityChip({ level, suffix = false }: { level: Level; suffix?: boolean }) {
  const { Icon, className } = SEVERITY[level];
  return (
    <span className={cn('inline-flex h-6 items-center gap-2 rounded-pill border px-3 text-micro', className)}>
      <Icon className="size-3.5 shrink-0" aria-hidden="true" />
      {suffix ? `${LEVEL_WORD[level]} severity` : LEVEL_WORD[level]}
    </span>
  );
}

function RiskDetail({
  risk,
  sources,
  onOpenSource,
}: {
  risk: Risk;
  sources: Map<string, SourceRecord>;
  onOpenSource: (key: string) => void;
}) {
  return (
    <div className="space-y-3">
      <p className="max-w-prose text-body text-content-secondary">
        {risk.description}{' '}
        <Citations sources={resolveStrategySources(sources, risk.sources)} onOpen={onOpenSource} />
      </p>
      <dl className="grid gap-2 text-small sm:grid-cols-[max-content_minmax(0,1fr)] sm:gap-x-4">
        <dt className="text-content-muted">Early warning sign</dt>
        <dd className="text-content-secondary">{risk.early_warning_signal}</dd>
        <dt className="text-content-muted">Confidence</dt>
        <dd className="text-content-secondary">{LEVEL_WORD[risk.confidence]}</dd>
      </dl>
      <BasisChip basis={risk.basis} />
    </div>
  );
}

function DetailToggle({
  open,
  controls,
  title,
  onToggle,
}: {
  open: boolean;
  controls: string;
  title: string;
  onToggle: () => void;
}) {
  return (
    <button
      type="button"
      aria-expanded={open}
      aria-controls={controls}
      onClick={onToggle}
      className={cn(
        'inline-flex min-h-[44px] items-center gap-1 rounded-control text-small text-primary sm:min-h-8',
        'hover:text-primary-hover hover:underline',
      )}
    >
      <ChevronDown className={cn('size-4 transition-transform duration-tab', open && 'rotate-180')} aria-hidden="true" />
      {open ? 'Hide details' : 'Show details'}
      <span className="sr-only"> for {title}</span>
    </button>
  );
}

export interface RisksSectionProps {
  swot: Swot;
  sources: Map<string, SourceRecord>;
  onOpenSource: (key: string) => void;
}

export function RisksSection({ swot, sources, onOpenSource }: RisksSectionProps) {
  const narrow = useMediaQuery(NARROW);
  const sortId = React.useId();
  const baseId = React.useId();
  const [sort, setSort] = React.useState<RiskSort>('severity');
  const [open, setOpen] = React.useState<Set<number>>(() => new Set());
  const risks = swot.risks ?? [];
  const coverage = swot.risk_category_coverage ?? {};
  const gaps = CATEGORIES.filter(
    (entry) => (swot.coverage_gaps ?? []).includes(entry.key) || (coverage[entry.key] ?? 0) === 0,
  );
  const shown = sortRisks(risks, sort).map((risk) => ({ risk, index: risks.indexOf(risk) }));
  const levels = (level: Level) => risks.filter((risk) => risk.severity === level).length;

  function toggle(index: number): void {
    setOpen((current) => {
      const next = new Set(current);
      if (next.has(index)) {
        next.delete(index);
      } else {
        next.add(index);
      }
      return next;
    });
  }

  return (
    <div className="space-y-6">
      <div className="space-y-3 rounded-panel border border-line bg-surface p-6">
        <p className="text-body text-content">
          {count(risks.length, 'risk')}: {levels('high')} high, {levels('medium')} medium, {levels('low')} low
        </p>
        <ul aria-label="Risks by category" className="flex flex-wrap gap-2">
          {CATEGORIES.map((entry) => {
            const found = coverage[entry.key] ?? 0;
            const gap = gaps.includes(entry);
            return (
              <li
                key={entry.key}
                className={cn(
                  'inline-flex h-6 items-center gap-2 rounded-pill border px-3 text-micro',
                  gap ? 'border-dashed border-line bg-surface text-content-secondary' : 'border-line bg-raised text-content',
                )}
              >
                {gap ? <CircleDashed className="size-3.5 shrink-0" aria-hidden="true" /> : null}
                {entry.label}: {gap ? 'none found' : count(found, 'risk')}
              </li>
            );
          })}
        </ul>
        {gaps.length > 0 ? (
          <p className="max-w-prose text-small text-content-muted">
            {words(gaps.map((entry) => entry.label))}: {GAP_NOTE}
          </p>
        ) : null}
      </div>

      {risks.length === 0 ? (
        <p className="max-w-prose text-small text-content-muted">{NONE_FOUND}</p>
      ) : (
        <>
          <div data-print-hide className="flex flex-wrap items-center gap-3">
            <label htmlFor={sortId} className="text-small text-content-secondary">
              Sort risks by
            </label>
            <select
              id={sortId}
              value={sort}
              onChange={(event) => setSort(event.target.value as RiskSort)}
              className={cn(controlClassName, 'min-h-[44px] w-auto sm:min-h-0')}
            >
              <option value="severity">Severity</option>
              <option value="category">Category</option>
            </select>
          </div>

          {narrow ? (
            <ul aria-label="Risk register" className="space-y-3">
              {shown.map(({ risk, index }) => {
                const detailId = `${baseId}-risk-${index}`;
                const expanded = open.has(index);
                return (
                  <li key={index}>
                    <article
                      aria-labelledby={`${detailId}-title`}
                      className="space-y-3 rounded-panel border border-line bg-surface p-4"
                    >
                      <h4 id={`${detailId}-title`} className="text-body font-medium text-content">
                        {risk.title}
                      </h4>
                      <div className="flex flex-wrap items-center gap-2">
                        <SeverityChip level={risk.severity} suffix />
                        <span className="inline-flex h-6 items-center rounded-pill border border-line bg-raised px-3 text-micro text-content">
                          {CATEGORY_LABEL[risk.category]}
                        </span>
                      </div>
                      <dl className="grid grid-cols-[max-content_minmax(0,1fr)] gap-x-4 gap-y-2 text-small">
                        <dt className="text-content-muted">Likelihood</dt>
                        <dd className="text-content-secondary">{LEVEL_WORD[risk.likelihood]}</dd>
                        <dt className="text-content-muted">Impact</dt>
                        <dd className="text-content-secondary">{LEVEL_WORD[risk.impact]}</dd>
                        <dt className="text-content-muted">Mitigation</dt>
                        <dd className="text-content-secondary">{risk.mitigation}</dd>
                      </dl>
                      <DetailToggle open={expanded} controls={detailId} title={risk.title} onToggle={() => toggle(index)} />
                      {expanded ? (
                        <div id={detailId} className="border-t border-line pt-3">
                          <RiskDetail risk={risk} sources={sources} onOpenSource={onOpenSource} />
                        </div>
                      ) : null}
                    </article>
                  </li>
                );
              })}
            </ul>
          ) : (
            <div className="overflow-x-auto rounded-panel border border-line bg-surface">
              <table className="w-full min-w-[56rem] text-small">
                <caption className="sr-only">
                  Risk register, sorted by {sort === 'severity' ? 'severity' : 'category'}.
                </caption>
                <thead>
                  <tr className="border-b border-line text-content-secondary">
                    {['Risk', 'Category', 'Likelihood', 'Impact', 'Severity', 'Mitigation'].map((column) => (
                      <th key={column} scope="col" className="px-4 py-3 text-left font-medium">
                        {column}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {shown.map(({ risk, index }) => {
                    const detailId = `${baseId}-risk-${index}`;
                    const expanded = open.has(index);
                    return (
                      <React.Fragment key={index}>
                        <tr className={cn('align-top', !expanded && 'border-b border-line')}>
                          <th scope="row" className="px-4 py-3 text-left font-medium text-content">
                            <span className="block">{risk.title}</span>
                            <DetailToggle
                              open={expanded}
                              controls={detailId}
                              title={risk.title}
                              onToggle={() => toggle(index)}
                            />
                          </th>
                          <td className="px-4 py-3 text-content-secondary">{CATEGORY_LABEL[risk.category]}</td>
                          <td className="px-4 py-3 text-content-secondary">{LEVEL_WORD[risk.likelihood]}</td>
                          <td className="px-4 py-3 text-content-secondary">{LEVEL_WORD[risk.impact]}</td>
                          <td className="px-4 py-3">
                            <SeverityChip level={risk.severity} />
                          </td>
                          <td className="max-w-[24rem] px-4 py-3 text-content-secondary">{risk.mitigation}</td>
                        </tr>
                        {expanded ? (
                          <tr id={detailId} className="border-b border-line">
                            <td colSpan={6} className="px-4 pb-4">
                              <RiskDetail risk={risk} sources={sources} onOpenSource={onOpenSource} />
                            </td>
                          </tr>
                        ) : null}
                      </React.Fragment>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  );
}
