/**
 * Stage tracker (KIRO_UI_UPGRADE_SPEC.md Sections 7.3 and 8.3).
 *
 * The old interface showed one spinner for up to two minutes. This shows the four stages with the
 * status and the time each one took, straight from GET /api/runs/{id}: nothing is guessed, and no
 * stage is shown as finished before the backend says so.
 *
 * Section 6.9: the running stage is announced in a live region, so the change is not visible only.
 */

import { Check, CircleDashed, Loader2, MinusCircle, XCircle, XOctagon } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import * as React from 'react';

import { Button } from '@/components/ui/button';
import { cn } from '@/lib/cn';
import { duration } from '@/lib/format';
import type { RunDetail, RunStage } from '@/features/run/useRun';

const LOOK: Record<RunStage['status'], { Icon: LucideIcon; tone: string; word: string; spin?: boolean }> = {
  waiting: { Icon: CircleDashed, tone: 'text-content-muted', word: 'Waiting' },
  running: { Icon: Loader2, tone: 'text-info', word: 'Running', spin: true },
  done: { Icon: Check, tone: 'text-success', word: 'Done' },
  skipped: { Icon: MinusCircle, tone: 'text-content-muted', word: 'Skipped' },
  failed: { Icon: XCircle, tone: 'text-danger', word: 'Failed' },
  cancelled: { Icon: XOctagon, tone: 'text-content-muted', word: 'Cancelled' },
};

export interface StageTrackerProps {
  run: RunDetail;
  onCancel: () => void;
  cancelling?: boolean;
  /** Shown when polling cannot reach the server (Section 8.2). */
  reconnecting?: boolean;
}

export function StageTracker({ run, onCancel, cancelling = false, reconnecting = false }: StageTrackerProps) {
  const running = run.stages.find((stage) => stage.status === 'running');

  // Only the stage that is running is announced, and only when it changes.
  const [announcement, setAnnouncement] = React.useState('');
  React.useEffect(() => {
    if (running) {
      setAnnouncement(`${running.label}: running`);
    } else if (run.state === 'done') {
      setAnnouncement('The validation finished. The results are below.');
    } else if (run.state === 'failed' || run.state === 'cancelled') {
      setAnnouncement(`The validation ${run.state === 'failed' ? 'could not finish' : 'was cancelled'}.`);
    }
  }, [running?.key, run.state, running]);

  return (
    <section aria-labelledby="progress-heading" className="space-y-4 rounded-panel border border-line bg-surface p-6">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h2 id="progress-heading">Analysing: {run.title}</h2>
        <p className="tabular text-small text-content-muted">Elapsed {duration(run.elapsed_s)}</p>
      </div>

      <p aria-live="polite" aria-atomic="true" className="sr-only">
        {announcement}
      </p>

      <ol className="space-y-1">
        {run.stages.map((stage) => {
          const { Icon, tone, word, spin } = LOOK[stage.status];
          return (
            <li
              key={stage.key}
              className="flex flex-wrap items-center gap-3 rounded-control px-2 py-2 even:bg-raised-soft"
            >
              <Icon className={cn('size-5 shrink-0', tone, spin && 'animate-spin')} aria-hidden="true" />
              <span className="min-w-0 flex-1 text-body text-content">{stage.label}</span>
              <span className={cn('text-small', tone)}>{word}</span>
              <span className="tabular w-20 text-right text-small text-content-muted">
                {stage.status === 'waiting' ? '' : duration(stage.elapsed_s)}
              </span>
              {stage.message ? (
                <p className="w-full pl-8 text-small text-content-muted">{stage.message}</p>
              ) : null}
            </li>
          );
        })}
      </ol>

      <div className="flex flex-wrap items-center gap-4">
        <Button variant="secondary" onClick={onCancel} loading={cancelling} disabled={run.cancel_requested}>
          {run.cancel_requested ? 'Stopping after this step' : 'Cancel run'}
        </Button>
        <p className="text-small text-content-muted">
          You can leave this page; the run keeps going.
        </p>
      </div>

      {run.cancel_requested && !cancelling ? (
        <p className="text-small text-content-muted">
          The step that is running finishes first, then the rest are skipped.
        </p>
      ) : null}

      {reconnecting ? (
        <p role="status" className="text-small text-warning">
          Lost connection. Retrying&#8230;
        </p>
      ) : null}
    </section>
  );
}
