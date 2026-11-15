/**
 * New validation (KIRO_UI_UPGRADE_SPEC.md Sections 7.1 and 7.2).
 *
 * Two steps on one page: the form, then the review. The form is kept mounted in state while the
 * review is open, so Back returns to exactly what was typed.
 *
 * Every failure shows the backend's own message (utils/errors.py), which is already written for the
 * user, and offers the action that can recover it. Nothing is reported as started unless the
 * backend answered with a run id.
 */

import { useQueryClient } from '@tanstack/react-query';
import * as React from 'react';
import { useLocation, useNavigate } from 'react-router-dom';

import { ApiError } from '@/api/client';
import { type ExtractedIdea, type IdeaSubmission, useExtractIdea, useStartRun } from '@/api/mutations';
import { queryKeys, useMeta } from '@/api/queries';
import { Alert } from '@/components/Alert';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { IdeaForm } from '@/features/new-validation/IdeaForm';
import { ReviewStep, type StrategyChoice } from '@/features/new-validation/ReviewStep';
import { type IdeaFormValues, joinCustomers, splitCustomers } from '@/features/new-validation/schema';
import { MESSAGES } from '@/lib/format';
import type { StrategyConstraints } from '@/lib/strategy';

/**
 * "Edit and re-run" sends the saved submission here through the router's state (Section 7.4), so
 * the form opens on what was asked last time. The chips are split back out of the one string the
 * backend stores.
 */
function fromSubmission(submission: IdeaSubmission): IdeaFormValues {
  return {
    idea_description: submission.idea_description,
    industry: submission.industry,
    target_customers: splitCustomers(submission.target_customers),
    relevant_details: submission.relevant_details ?? '',
  };
}

function toSubmission(values: IdeaFormValues): IdeaSubmission {
  const details = values.relevant_details.trim();
  return {
    idea_description: values.idea_description.trim(),
    industry: values.industry.trim(),
    target_customers: joinCustomers(values.target_customers),
    relevant_details: details === '' ? null : details,
  };
}

/** The wording for a failure, by what the backend said. */
function describe(error: unknown): { title: string; message: string } {
  if (!(error instanceof ApiError)) {
    return { title: 'Something went wrong', message: MESSAGES.failed };
  }
  if (error.isOffline) {
    return { title: 'The server is not running', message: error.message };
  }
  if (error.code === 'run_limit_reached') {
    return { title: 'A validation is already running', message: error.message };
  }
  if (error.status === 422) {
    return { title: 'The server rejected the form', message: error.message };
  }
  return { title: 'That step could not finish', message: error.message };
}

export function NewValidationPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const queryClient = useQueryClient();
  const meta = useMeta();
  const extract = useExtractIdea();
  const startRun = useStartRun();

  const carried = location.state as {
    prefill?: IdeaSubmission;
    constraints?: StrategyConstraints | null;
  } | null;
  const prefill = carried?.prefill;
  const [values, setValues] = React.useState<IdeaFormValues | null>(
    prefill ? fromSubmission(prefill) : null,
  );
  const [reviewing, setReviewing] = React.useState<{ submission: IdeaSubmission; idea: ExtractedIdea } | null>(null);

  function onSubmit(next: IdeaFormValues): void {
    setValues(next);
    const submission = toSubmission(next);
    extract.mutate(submission, {
      onSuccess: (idea) => setReviewing({ submission, idea }),
    });
  }

  function onRunAnalysis(idea: ExtractedIdea, strategy?: StrategyChoice): void {
    if (!reviewing) {
      return;
    }
    // Milestone 3: the strategy switch and only the constraints the founder filled.
    const extra = strategy
      ? {
          include_strategy: strategy.include_strategy,
          ...(strategy.constraints ? { constraints: strategy.constraints } : {}),
        }
      : {};
    startRun.mutate(
      { submission: reviewing.submission, idea_override: idea, ...extra },
      { onSuccess: (started) => navigate(`/runs/${started.run_id}`) },
    );
  }

  if (meta.isPending) {
    return (
      <div className="mx-auto max-w-form space-y-6" aria-busy="true">
        <h1>Check your startup idea</h1>
        <div className="space-y-4 rounded-panel border border-line bg-surface p-6">
          <Skeleton className="h-4 w-24" />
          <Skeleton className="h-32 w-full" />
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-40" />
        </div>
      </div>
    );
  }

  if (meta.isError || !meta.data) {
    const { title, message } = describe(meta.error);
    return (
      <div className="mx-auto max-w-form space-y-6">
        <h1>Check your startup idea</h1>
        <Alert
          tone="error"
          title={title}
          action={
            <Button variant="secondary" size="small" onClick={() => void meta.refetch()}>
              Try again
            </Button>
          }
        >
          {message}
        </Alert>
      </div>
    );
  }

  if (reviewing) {
    const failure = startRun.isError ? describe(startRun.error) : null;
    return (
      <div className="space-y-6">
        <div className="space-y-2">
          <h1>Review the idea we read</h1>
          <p className="max-w-prose text-body text-content-secondary">
            This is how the system understood your idea. Correct anything that is wrong, then start
            the research.
          </p>
        </div>
        {failure ? (
          <Alert tone="error" title={failure.title}>
            {failure.message}
          </Alert>
        ) : null}
        <ReviewStep
          meta={meta.data}
          submission={reviewing.submission}
          idea={reviewing.idea}
          constraints={carried?.constraints ?? null}
          busy={startRun.isPending}
          onRunAnalysis={onRunAnalysis}
          onBack={() => {
            setReviewing(null);
            startRun.reset();
          }}
        />
      </div>
    );
  }

  const failure = extract.isError ? describe(extract.error) : null;
  return (
    <div className="mx-auto max-w-form space-y-6">
      <div className="space-y-2">
        <h1>Check your startup idea</h1>
        <p className="max-w-prose text-body text-content-secondary">
          Describe it in two or three lines. We research the market and the competitors, and show
          where every finding came from.
        </p>
      </div>

      {failure ? (
        <Alert
          tone="error"
          title={failure.title}
          action={
            <Button
              variant="secondary"
              size="small"
              onClick={() => {
                extract.reset();
                void queryClient.invalidateQueries({ queryKey: queryKeys.meta });
              }}
            >
              Dismiss
            </Button>
          }
        >
          {failure.message}
        </Alert>
      ) : null}

      {prefill ? (
        <Alert tone="info" title="Loaded from an earlier validation">
          Change anything you want, then continue. This starts a new validation and leaves the
          earlier one as it is.
        </Alert>
      ) : null}

      <IdeaForm
        meta={meta.data}
        onSubmit={onSubmit}
        busy={extract.isPending}
        {...(values ? { defaultValues: values } : {})}
      />
    </div>
  );
}
