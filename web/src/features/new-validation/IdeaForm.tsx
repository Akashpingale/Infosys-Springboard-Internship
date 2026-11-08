/**
 * The submission form (KIRO_UI_UPGRADE_SPEC.md Sections 7.1 and 8.1).
 *
 * One action row inside the card: "Review my idea" runs extraction only, which takes about six
 * seconds, and then the review step opens. Every limit, industry and example comes from
 * GET /api/meta, so nothing here repeats a number the backend already owns.
 */

import { zodResolver } from '@hookform/resolvers/zod';
import { ChevronRight } from 'lucide-react';
import * as React from 'react';
import { Controller, useForm } from 'react-hook-form';

import type { MetaResponse } from '@/api/queries';
import { ChipInput, MAX_CHIPS } from '@/components/ChipInput';
import { Field, TextArea } from '@/components/Field';
import { IndustryCombobox } from '@/components/IndustryCombobox';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import {
  EMPTY_FORM,
  type IdeaFormValues,
  ideaFormSchema,
  joinCustomers,
  splitCustomers,
} from '@/features/new-validation/schema';

export interface IdeaFormProps {
  meta: MetaResponse;
  /** Called with the values once they pass the same rules the backend applies. */
  onSubmit: (values: IdeaFormValues) => void;
  /** True while extraction is in flight, which disables the action row (Section 8.1). */
  busy?: boolean;
  defaultValues?: IdeaFormValues;
}

export function IdeaForm({ meta, onSubmit, busy = false, defaultValues }: IdeaFormProps) {
  const limits = meta.limits;
  const schema = React.useMemo(() => ideaFormSchema(limits), [limits]);
  const {
    control,
    register,
    handleSubmit,
    reset,
    watch,
    formState: { errors },
  } = useForm<IdeaFormValues>({
    resolver: zodResolver(schema),
    defaultValues: defaultValues ?? EMPTY_FORM,
    // Section 7.1: check on blur, and again on submit.
    mode: 'onBlur',
  });

  const idea = watch('idea_description') ?? '';
  const details = watch('relevant_details') ?? '';
  const customers = watch('target_customers') ?? [];

  /*
   * The extra-context panel starts open when it already has text, which happens on "Edit and
   * re-run" and when an example is used: context the founder cannot see is context they cannot
   * correct. It is state rather than the bare attribute, so closing it again sticks.
   */
  const [contextOpen, setContextOpen] = React.useState(Boolean(defaultValues?.relevant_details?.trim()));

  function useExample(example: MetaResponse['examples'][number]): void {
    setContextOpen(Boolean(example.submission.relevant_details?.trim()));
    reset({
      idea_description: example.submission.idea_description,
      industry: example.submission.industry,
      target_customers: splitCustomers(example.submission.target_customers),
      relevant_details: example.submission.relevant_details ?? '',
    });
  }

  return (
    <form noValidate onSubmit={handleSubmit(onSubmit)} className="space-y-6">
      <div className="space-y-6 rounded-panel border border-line bg-surface p-6">
        <Field
          id="idea_description"
          label="Your idea"
          required
          helper={`${limits.idea_description.min_chars} to ${limits.idea_description.max_chars} characters, at least ${limits.idea_description.min_words} words.`}
          error={errors.idea_description?.message}
          counter={{ value: idea.trim().length, max: limits.idea_description.max_chars }}
        >
          {(field) => (
            <TextArea
              {...field}
              {...register('idea_description')}
              rows={5}
              disabled={busy}
              placeholder="A mobile app that detects crop diseases from a photo of a leaf and suggests a treatment."
            />
          )}
        </Field>

        <Field id="industry" label="Industry" required error={errors.industry?.message}>
          {(field) => (
            <Controller
              control={control}
              name="industry"
              render={({ field: { value, onChange, onBlur } }) => (
                <IndustryCombobox
                  {...field}
                  value={value}
                  onChange={onChange}
                  onBlur={onBlur}
                  industries={meta.industries}
                  disabled={busy}
                />
              )}
            />
          )}
        </Field>

        <Field
          id="target_customers"
          label="Target customers"
          required
          helper={`Type one and press Enter. Up to ${MAX_CHIPS}.`}
          error={
            errors.target_customers?.message ??
            (Array.isArray(errors.target_customers) ? undefined : errors.target_customers?.root?.message)
          }
          counter={{ value: joinCustomers(customers).length, max: limits.target_customers.max_chars }}
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
                  placeholder="Small farmers in Maharashtra"
                />
              )}
            />
          )}
        </Field>

        {/* Section 7.1: the rare extra context stays folded away until it is wanted. A native
            details element gives the keyboard and screen-reader behaviour without a dependency. */}
        <details
          open={contextOpen}
          onToggle={(event) => setContextOpen((event.currentTarget as HTMLDetailsElement).open)}
          className="group rounded-control border border-line bg-raised-soft"
        >
          <summary className="flex min-h-[44px] cursor-pointer items-center gap-2 px-3 py-2 text-body text-content sm:min-h-0">
            <ChevronRight className="size-4 transition-transform duration-tab group-open:rotate-90" aria-hidden="true" />
            Add more context (optional)
          </summary>
          <div className="px-3 pb-3 pt-1">
            <Field
              id="relevant_details"
              label="Anything else we should know?"
              helper={`Optional, up to ${limits.relevant_details.max_chars} characters.`}
              error={errors.relevant_details?.message}
              counter={{ value: details.trim().length, max: limits.relevant_details.max_chars }}
            >
              {(field) => (
                <TextArea
                  {...field}
                  {...register('relevant_details')}
                  rows={3}
                  disabled={busy}
                  placeholder="Location, stage, budget, competitors you already know about."
                />
              )}
            </Field>
          </div>
        </details>

        {/* Section 6.4: primary first, secondary beside it, both the same height. */}
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <Button type="submit" loading={busy} full className="sm:w-auto">
            {busy ? 'Reading your idea' : 'Review my idea'}
          </Button>
          <Button
            type="button"
            variant="text"
            disabled={busy}
            onClick={() => reset(EMPTY_FORM)}
            className="sm:w-auto"
          >
            Clear
          </Button>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <span className="text-small text-content-muted">Try an example:</span>
        {meta.examples.length === 0 ? (
          <Skeleton className="h-8 w-48" />
        ) : (
          meta.examples.map((example) => (
            <Button
              key={example.key}
              type="button"
              variant="secondary"
              size="small"
              disabled={busy}
              onClick={() => useExample(example)}
            >
              {example.label}
            </Button>
          ))
        )}
      </div>
    </form>
  );
}
