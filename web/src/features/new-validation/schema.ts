/**
 * Form rules (KIRO_UI_UPGRADE_SPEC.md Section 8.1).
 *
 * Every limit comes from GET /api/meta, which reports what models/schemas.py enforces, so no number
 * is written twice and the browser cannot disagree with the backend. The messages are the plain ones
 * from Section 6.7.
 */

import { z } from 'zod';

import type { MetaResponse } from '@/api/queries';
import type { BudgetLevel, ConstraintLimits, StrategyConstraints, TechnicalSkill } from '@/lib/strategy';

export const CUSTOMER_JOIN = ', ';

export type FormLimits = MetaResponse['limits'];

export interface IdeaFormValues {
  idea_description: string;
  industry: string;
  target_customers: string[];
  relevant_details: string;
}

export const EMPTY_FORM: IdeaFormValues = {
  idea_description: '',
  industry: '',
  target_customers: [],
  relevant_details: '',
};

/** The chips joined into the one string the backend takes. */
export function joinCustomers(chips: string[]): string {
  return chips.map((chip) => chip.trim()).filter(Boolean).join(CUSTOMER_JOIN);
}

/** A stored string split back into chips, for the edit-and-rerun path. */
export function splitCustomers(value: string): string[] {
  return value
    .split(/[,;]/)
    .map((part) => part.trim())
    .filter(Boolean);
}

function words(text: string): number {
  return text.trim().split(/\s+/).filter(Boolean).length;
}

/** The zod schema for the submission form, built from the backend's own limits. */
export function ideaFormSchema(limits: FormLimits) {
  const idea = limits.idea_description;
  const industry = limits.industry;
  const customers = limits.target_customers;
  const details = limits.relevant_details;
  const minChars = idea.min_chars ?? 0;
  const minWords = idea.min_words ?? 0;

  return z.object({
    idea_description: z
      .string()
      .trim()
      .min(1, 'Describe your startup idea.')
      .min(minChars, `Describe your idea in at least ${minChars} characters.`)
      .max(idea.max_chars, `Keep the idea to ${idea.max_chars} characters or fewer.`)
      .refine((value) => words(value) >= minWords, {
        message: `Describe your idea in at least ${minWords} words.`,
      }),
    industry: z
      .string()
      .trim()
      .min(1, 'Choose an industry, or type your own.')
      .min(industry.min_chars ?? 0, `Use at least ${industry.min_chars} characters for the industry.`)
      .max(industry.max_chars, `Keep the industry to ${industry.max_chars} characters or fewer.`),
    target_customers: z
      .array(z.string().trim().min(1))
      .min(1, 'Add at least one target customer.')
      .refine((chips) => joinCustomers(chips).length >= (customers.min_chars ?? 0), {
        message: `Describe your customers in at least ${customers.min_chars} characters.`,
      })
      .refine((chips) => joinCustomers(chips).length <= customers.max_chars, {
        message: `Keep the customers to ${customers.max_chars} characters or fewer in total.`,
      }),
    relevant_details: z
      .string()
      .trim()
      .max(details.max_chars, `Keep the extra context to ${details.max_chars} characters or fewer.`),
  });
}

export interface ReviewFormValues {
  idea_title: string;
  problem: string;
  solution: string;
  industry: string;
  target_customers: string[];
  key_features: string[];
}

/** The zod schema for the review step, built from the limits ExtractedIdea enforces. */
export function reviewFormSchema(limits: FormLimits) {
  const review = limits.extracted_idea;
  const customers = review.target_customers;
  const features = review.key_features;

  return z.object({
    idea_title: z
      .string()
      .trim()
      .min(1, 'Give the idea a short title.')
      .max(review.title_max_chars, `Keep the title to ${review.title_max_chars} characters or fewer.`),
    problem: z.string().trim().min(1, 'Say which problem the idea solves.'),
    solution: z.string().trim().min(1, 'Say how the idea solves it.'),
    industry: z.string().trim().min(1, 'Name the industry.'),
    target_customers: z
      .array(z.string().trim().min(1))
      .min(customers.min_items, `Keep at least ${customers.min_items} target customer.`)
      .max(customers.max_items, `Keep at most ${customers.max_items} target customers.`),
    key_features: z
      .array(z.string().trim().min(1))
      .min(features.min_items, `List at least ${features.min_items} key features.`)
      .max(features.max_items, `List at most ${features.max_items} key features.`),
  });
}

/**
 * The optional resources and goals (Milestone 3, Section 14.2). Every field is a string in the form,
 * and an empty one means "not given", so it is left out of the request rather than sent as a
 * default. The limits and choices are the ones GET /api/meta reports under `strategy.constraints`.
 */
export interface ConstraintFormValues {
  team_size: string;
  months_to_mvp: string;
  budget_level: string;
  technical_skill: string;
  launch_region: string;
}

export const EMPTY_CONSTRAINTS: ConstraintFormValues = {
  team_size: '',
  months_to_mvp: '',
  budget_level: '',
  technical_skill: '',
  launch_region: '',
};

const constraintFields = z.object({
  team_size: z.string(),
  months_to_mvp: z.string(),
  budget_level: z.string(),
  technical_skill: z.string(),
  launch_region: z.string(),
});

function inRange(value: string, min: number, max: number): boolean {
  const number = Number(value);
  return Number.isInteger(number) && number >= min && number <= max;
}

/** What is wrong with the constraints, field by field, against the backend's limits. */
export function constraintIssues(
  limits: ConstraintLimits,
  values: ConstraintFormValues,
): { field: keyof ConstraintFormValues; message: string }[] {
  const issues: { field: keyof ConstraintFormValues; message: string }[] = [];
  const team = limits.team_size;
  const months = limits.months_to_mvp;
  const region = limits.launch_region.max_chars;
  if (values.team_size !== '' && !inRange(values.team_size, team.min_value, team.max_value)) {
    issues.push({ field: 'team_size', message: `Choose a team size from ${team.min_value} to ${team.max_value}.` });
  }
  if (values.months_to_mvp !== '' && !inRange(values.months_to_mvp, months.min_value, months.max_value)) {
    issues.push({
      field: 'months_to_mvp',
      message: `Choose from ${months.min_value} to ${months.max_value} months.`,
    });
  }
  if (values.budget_level !== '' && !limits.budget_levels.includes(values.budget_level)) {
    issues.push({ field: 'budget_level', message: 'Choose one of the budget levels.' });
  }
  if (values.technical_skill !== '' && !limits.technical_skills.includes(values.technical_skill)) {
    issues.push({ field: 'technical_skill', message: 'Choose one of the skill levels.' });
  }
  if (values.launch_region.trim().length > region) {
    issues.push({ field: 'launch_region', message: `Keep the launch region to ${region} characters or fewer.` });
  }
  return issues;
}

/** The zod schema for the constraints on their own, for a form that holds nothing else. */
export function constraintsFormSchema(limits: ConstraintLimits) {
  return constraintFields.superRefine((values, context) => {
    for (const issue of constraintIssues(limits, values)) {
      context.addIssue({ code: z.ZodIssueCode.custom, path: [issue.field], message: issue.message });
    }
  });
}

export interface ReviewStepValues extends ReviewFormValues {
  include_strategy: boolean;
  constraints: ConstraintFormValues;
}

/**
 * The review step with the strategy switch and the constraints. The constraints are checked only
 * when strategy is offered and switched on, because they are not sent otherwise.
 */
export function reviewStepSchema(limits: FormLimits, constraints: ConstraintLimits | null) {
  return reviewFormSchema(limits)
    .extend({ include_strategy: z.boolean(), constraints: constraintFields })
    .superRefine((values, context) => {
      if (!constraints || !values.include_strategy) {
        return;
      }
      for (const issue of constraintIssues(constraints, values.constraints)) {
        context.addIssue({ code: z.ZodIssueCode.custom, path: ['constraints', issue.field], message: issue.message });
      }
    });
}

/** Only the fields the founder filled, or null when none was. */
export function toConstraints(values: ConstraintFormValues): StrategyConstraints | null {
  const constraints: StrategyConstraints = {};
  if (values.team_size !== '') {
    constraints.team_size = Number(values.team_size);
  }
  if (values.months_to_mvp !== '') {
    constraints.months_to_mvp = Number(values.months_to_mvp);
  }
  if (values.budget_level !== '') {
    constraints.budget_level = values.budget_level as BudgetLevel;
  }
  if (values.technical_skill !== '') {
    constraints.technical_skill = values.technical_skill as TechnicalSkill;
  }
  const region = values.launch_region.trim();
  if (region !== '') {
    constraints.launch_region = region;
  }
  return Object.keys(constraints).length > 0 ? constraints : null;
}

/** Stored constraints back into the form, for the edit-and-rerun path. */
export function fromConstraints(constraints: StrategyConstraints | null | undefined): ConstraintFormValues {
  return {
    team_size: constraints?.team_size == null ? '' : String(constraints.team_size),
    months_to_mvp: constraints?.months_to_mvp == null ? '' : String(constraints.months_to_mvp),
    budget_level: constraints?.budget_level ?? '',
    technical_skill: constraints?.technical_skill ?? '',
    launch_region: constraints?.launch_region ?? '',
  };
}

/** The first message of a failed zod parse, for a field the form does not own. */
export function firstMessage(error: z.ZodError): string {
  return error.issues[0]?.message ?? 'Check the form and try again.';
}
