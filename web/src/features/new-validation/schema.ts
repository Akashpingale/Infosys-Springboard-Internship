/**
 * Form rules (KIRO_UI_UPGRADE_SPEC.md Section 8.1).
 *
 * Every limit comes from GET /api/meta, which reports what models/schemas.py enforces, so no number
 * is written twice and the browser cannot disagree with the backend. The messages are the plain ones
 * from Section 6.7.
 */

import { z } from 'zod';

import type { MetaResponse } from '@/api/queries';

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

/** The first message of a failed zod parse, for a field the form does not own. */
export function firstMessage(error: z.ZodError): string {
  return error.issues[0]?.message ?? 'Check the form and try again.';
}
