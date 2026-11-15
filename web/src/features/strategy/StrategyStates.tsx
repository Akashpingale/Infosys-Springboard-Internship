import { zodResolver } from '@hookform/resolvers/zod';
import { CircleSlash, Compass } from 'lucide-react';
import * as React from 'react';
import { FormProvider, useForm } from 'react-hook-form';
import { z } from 'zod';

import { ApiError } from '@/api/client';
import { useMeta } from '@/api/queries';
import { Alert } from '@/components/Alert';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { ConstraintsPanel, type ConstraintsFields } from '@/features/new-validation/ConstraintsPanel';
import { constraintsFormSchema, fromConstraints, toConstraints } from '@/features/new-validation/schema';
import { isActive, type RunDetail } from '@/features/run/useRun';
import { MESSAGES } from '@/lib/format';
import type { PipelineResult } from '@/lib/results';
import type { ConstraintLimits, StrategyConstraints } from '@/lib/strategy';

export type StrategyStageKey = 'swot_risk' | 'mvp_recommendation' | 'go_to_market';

export type PartState =
  | { kind: 'ready' }
  | { kind: 'loading' }
  | { kind: 'failed'; reason: string | null }
  | { kind: 'skipped'; reason: string }
  | { kind: 'missing' };

export const STRATEGY_PARTS: { stage: StrategyStageKey; field: 'swot' | 'mvp' | 'gtm' }[] = [
  { stage: 'swot_risk', field: 'swot' },
  { stage: 'mvp_recommendation', field: 'mvp' },
  { stage: 'go_to_market', field: 'gtm' },
];

export const COPY = {
  empty:
    'No strategy yet. Generate a SWOT and risk review, an MVP plan and a go-to-market plan from these results. This uses 3 AI requests.',
  generate: 'Generate strategy',
  regenerate: 'Change resources and regenerate',
  failed: 'This part could not be completed.',
  failedRest: 'The rest of the strategy is below.',
  retry: 'Try again',
  skipped: 'This part was skipped because no analysis was available to build on.',
  notReady: 'There is no market or competitor analysis to build a strategy on.',
} as const;

const SKIPPED_CODE = 'strategy_stage_skipped';

export function partState(run: RunDetail, result: PipelineResult, stage: StrategyStageKey): PartState {
  const field = STRATEGY_PARTS.find((part) => part.stage === stage)?.field ?? 'swot';
  if (result[field]) {
    return { kind: 'ready' };
  }
  const row = run.stages.find((entry) => entry.key === stage);
  if (row && isActive(run.state) && (row.status === 'waiting' || row.status === 'running')) {
    return { kind: 'loading' };
  }
  const error = (result.errors ?? []).find((entry) => entry.stage === stage);
  if (error) {
    return { kind: 'failed', reason: error.message };
  }
  const skipped = (result.notices ?? []).find((entry) => entry.stage === stage && entry.code === SKIPPED_CODE);
  if (skipped || row?.status === 'skipped') {
    return { kind: 'skipped', reason: skipped?.message ?? row?.message ?? COPY.skipped };
  }
  if (row) {
    return { kind: 'failed', reason: row.message ?? null };
  }
  return { kind: 'missing' };
}

export function hasAnyStrategy(run: RunDetail, result: PipelineResult): boolean {
  return STRATEGY_PARTS.some((part) => partState(run, result, part.stage).kind !== 'missing');
}

export function canBuildStrategy(result: PipelineResult): boolean {
  return Boolean(result.idea) && Boolean(result.market || result.competitors);
}

export function errorText(error: unknown): string {
  return error instanceof ApiError ? error.message : MESSAGES.backendDown;
}

export function StrategyLoading({ label }: { label: string }) {
  return (
    <div aria-busy="true" className="space-y-3 rounded-panel border border-line bg-surface p-6">
      <p className="text-small text-content-muted">{label}</p>
      {[0, 1, 2].map((row) => (
        <Skeleton key={row} className="h-10 w-full" />
      ))}
    </div>
  );
}

export function StrategyFailed({
  reason,
  onRetry,
  busy,
}: {
  reason: string | null;
  onRetry?: () => void;
  busy?: boolean;
}) {
  return (
    <Alert
      tone="warning"
      title={COPY.failed}
      action={
        onRetry ? (
          <Button variant="secondary" size="small" onClick={onRetry} loading={busy}>
            {COPY.retry}
          </Button>
        ) : null
      }
    >
      {reason ? <p>{reason}</p> : null}
      <p>{COPY.failedRest}</p>
    </Alert>
  );
}

export function StrategySkipped({ reason }: { reason: string }) {
  return (
    <div className="flex items-start gap-3 rounded-panel border border-line bg-surface p-4">
      <CircleSlash className="mt-0.5 size-5 shrink-0 text-content-muted" aria-hidden="true" />
      <div className="space-y-1">
        <p className="text-body font-medium text-content">Skipped</p>
        <p className="max-w-prose text-body text-content-secondary">{reason}</p>
      </div>
    </div>
  );
}

export interface ResourcesFormProps {
  limits: ConstraintLimits;
  constraints: StrategyConstraints | null | undefined;
  submitLabel: string;
  onSubmit: (constraints: StrategyConstraints | null) => void;
  onCancel?: () => void;
  defaultOpen?: boolean;
  busy?: boolean;
  children?: React.ReactNode;
}

export function ResourcesForm({
  limits,
  constraints,
  submitLabel,
  onSubmit,
  onCancel,
  defaultOpen,
  busy = false,
  children,
}: ResourcesFormProps) {
  const schema = React.useMemo(() => z.object({ constraints: constraintsFormSchema(limits) }), [limits]);
  const carried = React.useMemo(() => fromConstraints(constraints), [constraints]);
  const methods = useForm<ConstraintsFields>({
    resolver: zodResolver(schema),
    defaultValues: { constraints: carried },
    mode: 'onBlur',
  });
  return (
    <FormProvider {...methods}>
      <form
        noValidate
        className="space-y-4"
        onSubmit={methods.handleSubmit((values) => onSubmit(toConstraints(values.constraints)))}
      >
        {children}
        <ConstraintsPanel
          limits={limits}
          defaultOpen={defaultOpen ?? toConstraints(carried) !== null}
          disabled={busy}
        />
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <Button type="submit" loading={busy} className="sm:w-auto">
            {submitLabel}
          </Button>
          {onCancel ? (
            <Button type="button" variant="text" disabled={busy} onClick={onCancel} className="sm:w-auto">
              Cancel
            </Button>
          ) : null}
        </div>
      </form>
    </FormProvider>
  );
}

export interface StrategyEmptyProps {
  run: RunDetail;
  result: PipelineResult;
  onGenerate: (constraints: StrategyConstraints | null) => void;
  busy: boolean;
  error: unknown;
}

export function StrategyEmpty({ run, result, onGenerate, busy, error }: StrategyEmptyProps) {
  const meta = useMeta();
  const strategy = meta.data?.strategy?.available ? meta.data.strategy : null;
  const ready = canBuildStrategy(result);
  return (
    <section aria-labelledby="strategy-empty-heading" className="space-y-4 rounded-panel border border-line bg-surface p-6">
      <Compass className="size-5 text-content-muted" aria-hidden="true" />
      <h2 id="strategy-empty-heading">Strategy</h2>
      <p className="max-w-prose text-body text-content-secondary">{COPY.empty}</p>
      {!ready ? (
        <p className="max-w-prose text-small text-content-muted">{COPY.notReady}</p>
      ) : strategy ? (
        <ResourcesForm
          limits={strategy.constraints}
          constraints={run.constraints}
          submitLabel={COPY.generate}
          onSubmit={onGenerate}
          busy={busy}
        />
      ) : null}
      {error ? (
        <Alert tone="error" title="The strategy was not started">
          {errorText(error)}
        </Alert>
      ) : null}
    </section>
  );
}
