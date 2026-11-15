/**
 * Review the extracted idea (KIRO_UI_UPGRADE_SPEC.md Section 7.2, feature 2, US-SUB-05).
 *
 * The missing step in the old interface: extraction takes about six seconds, and until now its
 * reading went straight into the expensive stages with no chance to correct it. Two columns on a
 * wide screen: what the founder wrote on the left, read-only, and how the system understood it on
 * the right, editable.
 *
 * Nothing is filled in on the founder's behalf: the fields hold exactly what extraction returned
 * until they are edited.
 */

import { zodResolver } from '@hookform/resolvers/zod';
import { Plus, X } from 'lucide-react';
import * as React from 'react';
import { Controller, FormProvider, useFieldArray, useForm } from 'react-hook-form';

import type { MetaResponse } from '@/api/queries';
import type { ExtractedIdea, IdeaSubmission } from '@/api/mutations';
import { ChipInput } from '@/components/ChipInput';
import { Field, TextArea, TextInput } from '@/components/Field';
import { Button } from '@/components/ui/button';
import { ConstraintsPanel } from '@/features/new-validation/ConstraintsPanel';
import {
  type ReviewStepValues,
  fromConstraints,
  reviewStepSchema,
  toConstraints,
} from '@/features/new-validation/schema';
import type { StrategyConstraints } from '@/lib/strategy';

/** Milestone 3 (Section 14.2): whether to run the strategy stages, and with which resources. */
export interface StrategyChoice {
  include_strategy: boolean;
  /** Only the fields the founder filled, or null. */
  constraints: StrategyConstraints | null;
}

export interface ReviewStepProps {
  meta: MetaResponse;
  /** What the founder wrote, shown as it was sent. */
  submission: IdeaSubmission;
  /** What extraction returned. */
  idea: ExtractedIdea;
  /** Constraints carried back by "Edit and re-run". They open the panel. */
  constraints?: StrategyConstraints | null;
  /** The strategy choice is passed only when the backend offers strategy. */
  onRunAnalysis: (idea: ExtractedIdea, strategy?: StrategyChoice) => void;
  onBack: () => void;
  busy?: boolean;
}

function Wrote({ label, value }: { label: string; value: string }) {
  return (
    <div className="space-y-1">
      <h3 className="text-small font-medium text-content-secondary">{label}</h3>
      <p className="whitespace-pre-wrap text-body text-content">{value}</p>
    </div>
  );
}

export function ReviewStep({
  meta,
  submission,
  idea,
  constraints,
  onRunAnalysis,
  onBack,
  busy = false,
}: ReviewStepProps) {
  const limits = meta.limits;
  // Strategy is offered only when the backend says every strategy stage can run.
  const strategy = meta.strategy?.available ? meta.strategy : null;
  const constraintLimits = strategy?.constraints ?? null;
  const schema = React.useMemo(() => reviewStepSchema(limits, constraintLimits), [limits, constraintLimits]);
  const carried = React.useMemo(() => fromConstraints(constraints), [constraints]);
  const methods = useForm<ReviewStepValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      idea_title: idea.idea_title,
      problem: idea.problem,
      solution: idea.solution,
      industry: idea.industry,
      target_customers: [...idea.target_customers],
      key_features: [...idea.key_features],
      include_strategy: strategy !== null,
      constraints: carried,
    },
    mode: 'onBlur',
  });
  const {
    control,
    register,
    handleSubmit,
    watch,
    formState: { errors },
  } = methods;
  const features = useFieldArray({ control, name: 'key_features' as never });
  const featureLimits = limits.extracted_idea.key_features;
  const includeStrategy = watch('include_strategy');

  return (
    <form
      noValidate
      onSubmit={handleSubmit((values) => {
        const reviewed: ExtractedIdea = {
          idea_title: values.idea_title.trim(),
          problem: values.problem.trim(),
          solution: values.solution.trim(),
          industry: values.industry.trim(),
          target_customers: values.target_customers.map((entry) => entry.trim()),
          key_features: values.key_features.map((entry) => entry.trim()),
        };
        if (!strategy) {
          onRunAnalysis(reviewed);
          return;
        }
        onRunAnalysis(reviewed, {
          include_strategy: values.include_strategy,
          constraints: values.include_strategy ? toConstraints(values.constraints) : null,
        });
      })}
      className="space-y-6"
    >
      <div className="grid gap-6 lg:grid-cols-2">
        <section aria-labelledby="wrote-heading" className="space-y-4 rounded-panel border border-line bg-surface p-6">
          <h2 id="wrote-heading">What you wrote</h2>
          <Wrote label="Your idea" value={submission.idea_description} />
          <Wrote label="Industry" value={submission.industry} />
          <Wrote label="Target customers" value={submission.target_customers} />
          {submission.relevant_details ? <Wrote label="More context" value={submission.relevant_details} /> : null}
        </section>

        <section aria-labelledby="understood-heading" className="space-y-6 rounded-panel border border-line bg-surface p-6">
          <div className="space-y-1">
            <h2 id="understood-heading">How we understood it</h2>
            <p className="max-w-prose text-small text-content-muted">
              Correct anything that is wrong before the research runs.
            </p>
          </div>

          <Field id="idea_title" label="Title" required error={errors.idea_title?.message}>
            {(field) => <TextInput {...field} {...register('idea_title')} disabled={busy} />}
          </Field>

          <Field id="problem" label="Problem" required error={errors.problem?.message}>
            {(field) => <TextArea {...field} {...register('problem')} rows={3} disabled={busy} />}
          </Field>

          <Field id="solution" label="Solution" required error={errors.solution?.message}>
            {(field) => <TextArea {...field} {...register('solution')} rows={3} disabled={busy} />}
          </Field>

          <Field id="review_industry" label="Industry" required error={errors.industry?.message}>
            {(field) => <TextInput {...field} {...register('industry')} disabled={busy} />}
          </Field>

          <Field
            id="review_customers"
            label="Target customers"
            required
            helper={`${limits.extracted_idea.target_customers.min_items} to ${limits.extracted_idea.target_customers.max_items}.`}
            error={
              errors.target_customers?.message ??
              (Array.isArray(errors.target_customers) ? undefined : errors.target_customers?.root?.message)
            }
          >
            {(field) => (
              <Controller
                control={control}
                name="target_customers"
                render={({ field: { value, onChange, onBlur } }) => (
                  <ChipInput
                    {...field}
                    value={value}
                    onChange={onChange}
                    onBlur={onBlur}
                    disabled={busy}
                    max={limits.extracted_idea.target_customers.max_items}
                  />
                )}
              />
            )}
          </Field>

          <fieldset className="space-y-2">
            <legend className="text-body font-medium text-content">
              Key features
              <span aria-hidden="true" className="ml-1 text-content-muted">
                *
              </span>
            </legend>
            <p className="text-small text-content-muted">
              {featureLimits.min_items} to {featureLimits.max_items}.
            </p>
            <ul className="space-y-2">
              {features.fields.map((entry, index) => (
                <li key={entry.id} className="flex items-center gap-2">
                  <TextInput
                    {...register(`key_features.${index}` as const)}
                    aria-label={`Key feature ${index + 1}`}
                    disabled={busy}
                  />
                  <Button
                    type="button"
                    variant="secondary"
                    size="icon"
                    disabled={busy || features.fields.length <= featureLimits.min_items}
                    onClick={() => features.remove(index)}
                    aria-label={`Remove key feature ${index + 1}`}
                  >
                    <X aria-hidden="true" />
                  </Button>
                </li>
              ))}
            </ul>
            {errors.key_features?.message ?? errors.key_features?.root?.message ? (
              <p className="text-small text-danger">
                {errors.key_features?.message ?? errors.key_features?.root?.message}
              </p>
            ) : null}
            <Button
              type="button"
              variant="secondary"
              size="small"
              disabled={busy || features.fields.length >= featureLimits.max_items}
              onClick={() => features.append('' as never)}
            >
              <Plus aria-hidden="true" />
              Add a feature
            </Button>
          </fieldset>
        </section>
      </div>

      {strategy ? (
        <section aria-labelledby="strategy-heading" className="space-y-4 rounded-panel border border-line bg-surface p-6">
          <h2 id="strategy-heading">Strategy</h2>
          <div className="space-y-1">
            <label
              htmlFor="include_strategy"
              className="inline-flex min-h-[44px] cursor-pointer items-center gap-3 text-body font-medium text-content"
            >
              <input
                id="include_strategy"
                type="checkbox"
                role="switch"
                aria-describedby="include_strategy-helper"
                className="size-5 accent-primary"
                disabled={busy}
                {...register('include_strategy')}
              />
              Include strategy
            </label>
            <p id="include_strategy-helper" className="max-w-prose text-small text-content-muted">
              Adds a SWOT and risk review, an MVP plan and a go-to-market plan. Uses 3 more AI requests and
              about 1 to 2 minutes.
            </p>
          </div>
          {includeStrategy ? (
            <FormProvider {...methods}>
              <ConstraintsPanel
                limits={strategy.constraints}
                defaultOpen={toConstraints(carried) !== null}
                disabled={busy}
              />
            </FormProvider>
          ) : null}
        </section>
      ) : null}

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <Button type="submit" loading={busy} full className="sm:w-auto">
          {busy ? 'Starting the analysis' : 'Run analysis'}
        </Button>
        <Button type="button" variant="text" disabled={busy} onClick={onBack} className="sm:w-auto">
          Back
        </Button>
      </div>
      <p className="max-w-prose text-small text-content-muted">
        Next we search the web and analyse the market and competitors. This takes about two minutes.
      </p>
    </form>
  );
}
