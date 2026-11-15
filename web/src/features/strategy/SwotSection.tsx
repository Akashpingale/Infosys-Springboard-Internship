import type { components } from '@/api/types.gen';
import { BasisChip } from '@/components/BasisChip';
import { Citations } from '@/components/CitationChip';
import { cn } from '@/lib/cn';
import { count } from '@/lib/format';
import {
  SWOT_QUADRANTS,
  resolveStrategySources,
  type PipelineResult,
  type SourceRecord,
  type StrategySourceKey,
} from '@/lib/results';

type Swot = NonNullable<PipelineResult['swot']>;
type StrategyBasis = components['schemas']['SwotItem']['basis'];

export const NONE_FOUND = 'None found in this run.';

export interface StrategyClaimProps {
  text: string;
  detail?: string;
  basis: StrategyBasis;
  refs: StrategySourceKey[] | undefined;
  sources: Map<string, SourceRecord>;
  onOpenSource: (key: string) => void;
  className?: string;
}

export function StrategyClaim({ text, detail, basis, refs, sources, onOpenSource, className }: StrategyClaimProps) {
  return (
    <li data-claim="" className={cn('space-y-2', className)}>
      <p className="max-w-prose text-body text-content-secondary">
        {text}{' '}
        <Citations sources={resolveStrategySources(sources, refs)} onOpen={onOpenSource} />
      </p>
      {detail ? <p className="max-w-prose text-small text-content-muted">{detail}</p> : null}
      <BasisChip basis={basis} />
    </li>
  );
}

export interface SwotSectionProps {
  swot: Swot;
  sources: Map<string, SourceRecord>;
  onOpenSource: (key: string) => void;
}

export function SwotSection({ swot, sources, onOpenSource }: SwotSectionProps) {
  return (
    <div className="space-y-6">
      <div className="grid gap-4 lg:grid-cols-2">
        {SWOT_QUADRANTS.map((quadrant) => {
          const items = swot[quadrant.key] ?? [];
          const headingId = `swot-${quadrant.key}-heading`;
          return (
            <section
              key={quadrant.key}
              aria-labelledby={headingId}
              className="min-w-0 space-y-4 rounded-panel border border-line bg-surface p-6"
            >
              <div className="flex flex-wrap items-baseline justify-between gap-3">
                <h3 id={headingId}>{quadrant.label}</h3>
                <span className="tabular text-small text-content-muted">{count(items.length, 'point')}</span>
              </div>
              {items.length === 0 ? (
                <p className="max-w-prose text-small text-content-muted">{NONE_FOUND}</p>
              ) : (
                <ul className="space-y-4">
                  {items.map((item, index) => (
                    <StrategyClaim
                      key={`${quadrant.key}-${index}`}
                      text={item.text}
                      detail={item.why_it_matters || undefined}
                      basis={item.basis}
                      refs={item.sources}
                      sources={sources}
                      onOpenSource={onOpenSource}
                    />
                  ))}
                </ul>
              )}
            </section>
          );
        })}
      </div>
      {swot.summary ? (
        <div className="space-y-2 rounded-panel border border-line bg-surface p-6">
          <p className="max-w-prose text-body text-content-secondary">{swot.summary}</p>
          <BasisChip basis="ai_interpretation" />
        </div>
      ) : null}
    </div>
  );
}
