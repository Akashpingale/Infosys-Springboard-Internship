/**
 * Fixtures for the MSW tests.
 *
 * The meta reply mirrors what GET /api/meta really returns, with the limits models/schemas.py
 * enforces, so a test cannot pass against limits the backend does not have.
 */

import type { ExtractedIdea } from '@/api/mutations';
import type { MetaResponse } from '@/api/queries';

export const INDUSTRIES = [
  'Agriculture / AgriTech',
  'Healthcare / HealthTech',
  'Finance / FinTech',
  'Food & Beverage',
  'Other',
];

export const META: MetaResponse = {
  app_name: 'AI Startup Idea Validator',
  version: '0.1.0',
  limits: {
    idea_description: { min_chars: 30, max_chars: 2000, min_words: 3 },
    industry: { min_chars: 2, max_chars: 60, min_words: null },
    target_customers: { min_chars: 3, max_chars: 300, min_words: null },
    relevant_details: { min_chars: null, max_chars: 1500, min_words: null },
    extracted_idea: {
      title_max_chars: 80,
      target_customers: { min_items: 1, max_items: 5 },
      key_features: { min_items: 3, max_items: 6 },
    },
  },
  industries: INDUSTRIES,
  examples: [
    {
      key: 'agritech',
      label: 'Agritech',
      submission: {
        idea_description:
          'A mobile app that detects crop diseases from a photo of a leaf and suggests a treatment for small farmers.',
        industry: 'Agriculture / AgriTech',
        target_customers: 'Small farmers in India, Agricultural cooperatives',
        relevant_details: 'Starting with two farming cooperatives.',
      },
    },
    {
      key: 'fintech_cashflow',
      label: 'Fintech',
      submission: {
        idea_description:
          'A cash-flow and expense management platform for small businesses that reads their bank statements.',
        industry: 'Finance / FinTech',
        target_customers: 'Small business owners',
        relevant_details: null,
      },
    },
  ],
  stages: [
    { key: 'extraction', label: 'Understanding your idea' },
    { key: 'search', label: 'Searching the web' },
    { key: 'market_opportunity', label: 'Analysing the market' },
    { key: 'competitor_analysis', label: 'Comparing competitors' },
  ],
  run_limits: {
    time_limit_s: 162,
    max_concurrent_runs: 2,
    competitor_max_extra_queries: 5,
    competitor_results_per_query: 3,
    evidence_max_items: 12,
  },
  providers: {
    llm: { name: 'Gemini', configured: true, model: 'gemini-3-flash-preview' },
    fallback_llm: { name: 'Groq', configured: true, model: 'openai/gpt-oss-120b' },
    search: { name: 'Tavily', configured: true },
  },
};

export const EXTRACTED: ExtractedIdea = {
  idea_title: 'CropScan: AI crop disease detection',
  problem: 'Small farmers lose crops because diseases are spotted too late.',
  solution: 'A phone app that detects crop diseases from a photo and suggests a treatment.',
  target_customers: ['Small farmers in India', 'Agricultural cooperatives'],
  industry: 'Agriculture / AgriTech',
  key_features: ['Photo-based diagnosis', 'Treatment advice', 'Local language support'],
};

/** A valid idea description: over 30 characters and more than three words. */
export const VALID_IDEA =
  'A mobile app that detects crop diseases from a photo of a leaf and suggests a treatment.';
