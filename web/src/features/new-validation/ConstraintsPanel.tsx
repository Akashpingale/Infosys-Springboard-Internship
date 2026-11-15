import { ChevronRight } from 'lucide-react';
import * as React from 'react';
import { useFormContext } from 'react-hook-form';

import { Field, TextInput, controlClassName } from '@/components/Field';
import type { ConstraintFormValues } from '@/features/new-validation/schema';
import { cn } from '@/lib/cn';
import { budgetLabel, range, skillLabel, type ConstraintLimits } from '@/lib/strategy';

export interface ConstraintsFields {
  constraints: ConstraintFormValues;
}

export interface ConstraintsPanelProps {
  limits: ConstraintLimits;
  defaultOpen?: boolean;
  disabled?: boolean;
}

function RadioGroup({
  name,
  legend,
  options,
  label,
  error,
  disabled,
}: {
  name: 'constraints.budget_level' | 'constraints.technical_skill';
  legend: string;
  options: string[];
  label: (value: string) => string;
  error: string | undefined;
  disabled: boolean;
}) {
  const { register } = useFormContext<ConstraintsFields>();
  const errorId = `${name.replace('.', '-')}-error`;
  return (
    <fieldset className="space-y-2" aria-describedby={error ? errorId : undefined}>
      <legend className="text-body font-medium text-content">{legend}</legend>
      <div className="flex flex-wrap gap-x-4 gap-y-1">
        {options.map((option) => (
          <label
            key={option}
            className="inline-flex min-h-[44px] cursor-pointer items-center gap-2 text-body text-content"
          >
            <input
              type="radio"
              value={option}
              disabled={disabled}
              className="size-4 accent-primary"
              {...register(name)}
            />
            {label(option)}
          </label>
        ))}
      </div>
      {error ? (
        <p id={errorId} className="text-small text-danger">
          {error}
        </p>
      ) : null}
    </fieldset>
  );
}

export function ConstraintsPanel({ limits, defaultOpen = false, disabled = false }: ConstraintsPanelProps) {
  const {
    register,
    watch,
    formState: { errors },
  } = useFormContext<ConstraintsFields>();
  const [open, setOpen] = React.useState(defaultOpen);
  const fieldErrors = errors.constraints;
  const region = watch('constraints.launch_region') ?? '';
  const selectClass = cn(controlClassName, 'min-h-[44px] sm:min-h-0');

  return (
    <details
      open={open}
      onToggle={(event) => setOpen((event.currentTarget as HTMLDetailsElement).open)}
      className="group rounded-control border border-line bg-raised-soft"
    >
      <summary className="flex min-h-[44px] cursor-pointer items-center gap-2 px-3 py-2 text-body text-content sm:min-h-0">
        <ChevronRight className="size-4 transition-transform duration-tab group-open:rotate-90" aria-hidden="true" />
        Resources and goals (optional)
      </summary>
      <div className="space-y-5 px-3 pb-4 pt-1">
        <p className="max-w-prose text-small text-content-muted">
          If you skip these, the plan assumes a team of 2 and 3 months, and marks that as an assumption.
        </p>

        <div className="grid gap-5 sm:grid-cols-2">
          <Field id="constraints_team_size" label="Team size" error={fieldErrors?.team_size?.message}>
            {(field) => (
              <select {...field} {...register('constraints.team_size')} disabled={disabled} className={selectClass}>
                <option value="">Not set</option>
                {range(limits.team_size.min_value, limits.team_size.max_value).map((size) => (
                  <option key={size} value={String(size)}>
                    {size === 1 ? '1 person' : `${size} people`}
                  </option>
                ))}
              </select>
            )}
          </Field>

          <Field
            id="constraints_months_to_mvp"
            label="Months to first release"
            error={fieldErrors?.months_to_mvp?.message}
          >
            {(field) => (
              <select {...field} {...register('constraints.months_to_mvp')} disabled={disabled} className={selectClass}>
                <option value="">Not set</option>
                {range(limits.months_to_mvp.min_value, limits.months_to_mvp.max_value).map((months) => (
                  <option key={months} value={String(months)}>
                    {months === 1 ? '1 month' : `${months} months`}
                  </option>
                ))}
              </select>
            )}
          </Field>
        </div>

        <RadioGroup
          name="constraints.budget_level"
          legend="Budget level"
          options={limits.budget_levels}
          label={budgetLabel}
          error={fieldErrors?.budget_level?.message}
          disabled={disabled}
        />

        <RadioGroup
          name="constraints.technical_skill"
          legend="Technical skill"
          options={limits.technical_skills}
          label={skillLabel}
          error={fieldErrors?.technical_skill?.message}
          disabled={disabled}
        />

        <Field
          id="constraints_launch_region"
          label="Launch region"
          helper={`Optional, up to ${limits.launch_region.max_chars} characters.`}
          error={fieldErrors?.launch_region?.message}
          counter={{ value: region.trim().length, max: limits.launch_region.max_chars }}
        >
          {(field) => (
            <TextInput
              {...field}
              {...register('constraints.launch_region')}
              disabled={disabled}
              placeholder="Pune, India"
            />
          )}
        </Field>
      </div>
    </details>
  );
}
