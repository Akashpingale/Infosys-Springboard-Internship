/**
 * Fixtures for the run page.
 *
 * Shaped exactly like what the backend returns, including the part that matters most for citation
 * chips: the market and the competitor analyses each number their own evidence, so `S1` appears in
 * both and points at a different page in each.
 */

import type { RunDetail, RunStage } from '@/features/run/useRun';
import type { PipelineResult } from '@/lib/results';

export const MARKET_S1_URL = 'https://reports.example/crop-ai-market';
export const COMPETITOR_S1_URL = 'https://khatabook.example/pricing';

const MARKET = {
  industry_overview: {
    summary: 'AI crop disease detection is a growing part of AgriTech.',
    market_category: 'AI crop disease detection',
    developments: [
      {
        text: 'A startup launched drone-based disease scouting for cooperatives.',
        basis: 'sourced',
        source_ids: ['S1'],
      },
    ],
  },
  market_demand: {
    summary: 'Small farmers lose crops when diseases are spotted late.',
    demand_evidence: [
      {
        text: 'Most small farmers say they lose crops because diseases are spotted late.',
        basis: 'sourced',
        source_ids: ['S1'],
      },
      {
        text: 'Photo diagnosis apps already reach farmers in their own languages.',
        basis: 'ai_interpretation',
        source_ids: ['S0'],
      },
    ],
    customer_problems: [],
    interest_signals: [],
  },
  market_size: {
    tam: {
      value: 'USD 1.8 billion',
      status: 'sourced',
      source_ids: ['S1'],
      note: 'AI crop disease detection market, 2025',
      scope: 'idea_market',
    },
    sam: { value: null, status: 'unavailable', source_ids: [], note: null, scope: null },
    som: { value: null, status: 'unavailable', source_ids: [], note: null, scope: null },
  },
  broader_markets: [],
  trends: [
    { trend: 'Drone-based disease scouting', category: 'technology', basis: 'sourced', source_ids: ['S1'] },
  ],
  segments: [
    {
      name: 'Smallholder farmers',
      description: 'Farmers on small plots who lose crops to late diagnosis.',
      segmentation_basis: 'business_type',
      needs: ['Early disease warnings'],
      pain_points: [{ text: 'Crops lost to late diagnosis', basis: 'sourced', source_ids: ['S1'] }],
      source_ids: ['S1'],
    },
    {
      name: 'Farming cooperatives',
      description: 'Groups that advise many member farmers.',
      segmentation_basis: 'business_type',
      needs: ['Scouting across many fields'],
      pain_points: [{ text: 'Few experts per member', basis: 'assumption', source_ids: [] }],
      source_ids: [],
    },
  ],
  priority_segment: {
    segment_name: 'Smallholder farmers',
    rationale: 'They feel the crop losses most directly.',
    risks: ['Free diagnosis apps already serve them'],
  },
  opportunities: [
    { text: 'Treatment advice in local languages', basis: 'ai_interpretation', source_ids: ['S0'] },
    { text: 'Start with the two cooperatives you already know', basis: 'user_provided', source_ids: [] },
  ],
  limitations: [{ text: 'A free photo diagnosis app already exists', basis: 'sourced', source_ids: ['S1'] }],
  sources: [
    { id: 'S0', title: 'Search engine summary', url: '' },
    { id: 'S1', title: 'Crop AI market report', url: MARKET_S1_URL },
  ],
  data_quality: { evidence_level: 'limited', notes: ['No market figure for India was found.'] },
  caveats: ['Market figures are evidence-dependent and need verification.'],
} as unknown as NonNullable<PipelineResult['market']>;

const COMPETITORS = {
  competitors: [
    {
      name: 'Plantix',
      type: 'direct',
      relevance_note: 'Also diagnoses crop disease from a photo.',
      website: null,
      source_ids: ['S1'],
      offering: 'Photo-based crop diagnosis',
      target_segment: 'Smallholder farmers',
      key_features: ['Photo diagnosis', 'Treatment advice'],
      value_proposition: 'Free diagnosis at scale',
      pricing_model: { value: null, status: 'unavailable', source_ids: [], note: null },
      strengths: [{ text: 'Large existing user base', basis: 'sourced', source_ids: ['S1'] }],
      weaknesses: [],
      positioning: 'Free consumer app',
      differentiation_vs_startup: 'No cooperative features',
      basis: 'sourced',
      info_completeness: 'partial',
    },
    {
      name: 'Local agronomists',
      type: 'indirect',
      relevance_note: 'Farmers ask them instead.',
      website: null,
      source_ids: ['S2'],
      offering: 'In-person advice',
      target_segment: 'Smallholder farmers',
      key_features: ['Field visits'],
      value_proposition: 'Trusted local advice',
      pricing_model: { value: null, status: 'unavailable', source_ids: [], note: null },
      strengths: [],
      weaknesses: [],
      positioning: 'Traditional advice',
      differentiation_vs_startup: 'Not instant',
      basis: 'sourced',
      info_completeness: 'minimal',
    },
  ],
  comparison: {
    features: ['Photo diagnosis', 'Treatment advice'],
    rows: [
      {
        competitor: 'Plantix',
        cells: [
          { feature: 'Photo diagnosis', status: 'evidence_found', source_ids: ['S1'] },
          { feature: 'Treatment advice', status: 'no_evidence_found', source_ids: [] },
        ],
      },
    ],
    feature_coverage: [
      { feature: 'Photo diagnosis', competitors_with_evidence: 1 },
      { feature: 'Treatment advice', competitors_with_evidence: 0 },
    ],
  },
  market_gaps: [
    {
      description: 'No competitor offers advice in local languages for cooperatives',
      related_features: ['Treatment advice'],
      basis: 'ai_interpretation',
      source_ids: ['S1'],
      confidence: 'medium',
      caveat: 'Absence from search results does not prove a competitor or a gap does not exist.',
    },
  ],
  differentiation_opportunities: [
    { text: 'Serve cooperatives rather than single farmers', basis: 'ai_interpretation', source_ids: ['S2'] },
  ],
  queries_used: ['Plantix pricing features'],
  sources: [
    { id: 'S1', title: 'Khatabook pricing page', url: COMPETITOR_S1_URL },
    { id: 'S2', title: 'Agronomist directory', url: 'https://agronomists.example/list' },
  ],
  data_quality: { evidence_level: 'limited', notes: [] },
  caveats: ['Absence from search results does not prove a competitor or a gap does not exist.'],
} as unknown as NonNullable<PipelineResult['competitors']>;

export const COMPLETE_RESULT: PipelineResult = {
  status: 'complete',
  idea: {
    idea_title: 'CropScan: AI crop disease detection',
    problem: 'Small farmers lose crops because diseases are spotted too late.',
    solution: 'A phone app that detects crop diseases from a photo.',
    target_customers: ['Small farmers in India'],
    industry: 'Agriculture / AgriTech',
    key_features: ['Photo diagnosis', 'Treatment advice', 'Local languages'],
  },
  search: null,
  warnings: ['Market opportunity: segments[1].pain_points[0]: it is not about the problem this idea solves, so it was removed'],
  errors: [],
  timings: { extraction: 6.5, search: 18.2, market_opportunity: 27.3, competitor_analysis: 56.9, total: 108.9 },
  market: MARKET,
  competitors: COMPETITORS,
  market_search: null,
  competitor_candidates: [],
  competitor_search: null,
  notices: [
    {
      stage: 'market_opportunity',
      code: 'off_topic_removed',
      severity: 'info',
      message: 'One pain point was removed because it was not about the problem your idea solves.',
      detail:
        'Market opportunity: segments[1].pain_points[0]: it is not about the problem this idea solves, so it was removed',
    },
    {
      stage: 'competitor_analysis',
      code: 'candidates_failed',
      severity: 'warning',
      message:
        'Competitor names could not be listed from the first search, so only general competitor searches were run.',
      detail: 'Competitor analysis: Phase A: the candidate search failed (busy), so only the generic searches were used',
    },
  ],
  evidence_strength: {
    label: 'moderate',
    score: 0.674,
    caption: 'How well the findings are backed by sources. This is not a prediction of success.',
    components: [
      {
        key: 'sourced_share',
        label: 'Sourced share',
        weight: 0.4,
        value: 0.56,
        detail: '7 of 12 labelled claims are backed by a cited source.',
      },
      {
        key: 'source_breadth',
        label: 'Source breadth',
        weight: 0.3,
        value: 1,
        detail: '3 distinct source websites, counted up to 8.',
      },
      {
        key: 'evidence_level',
        label: 'Evidence level',
        weight: 0.3,
        value: 0.5,
        detail: 'Market evidence rated limited; Competitor evidence rated limited.',
      },
    ],
  },
  executive_summary: [
    {
      topic: 'market_size',
      text: 'Market size (TAM): USD 1.8 billion (AI crop disease detection market, 2025).',
      basis: 'sourced',
      source_ids: ['S1'],
      analysis: 'market',
    },
    {
      topic: 'competitors',
      text: '2 competitors found: 1 direct and 1 indirect.',
      basis: null,
      source_ids: [],
      analysis: 'competitors',
    },
    {
      topic: 'gap',
      text: 'Possible gap (medium confidence, a hypothesis): No competitor offers advice in local languages for cooperatives.',
      basis: 'ai_interpretation',
      source_ids: ['S1'],
      analysis: 'competitors',
    },
  ],
  verify_next: [
    {
      topic: 'market_size',
      text: "Find a reliable market size for this idea's own market: no source confirmed the SAM or SOM.",
      source_ids: [],
      analysis: 'market',
    },
    {
      topic: 'competitor',
      text: 'Find out more about Local agronomists: the sources gave little detail.',
      source_ids: ['S2'],
      analysis: 'competitors',
    },
  ],
};

function stage(key: string, label: string, status: RunStage['status'], elapsed?: number): RunStage {
  return {
    key,
    label,
    status,
    started_at: status === 'waiting' ? null : '2026-10-29T10:00:00.000+00:00',
    duration_s: elapsed ?? null,
    elapsed_s: elapsed ?? null,
    message: null,
  };
}

const BASE: Omit<RunDetail, 'state' | 'stages' | 'result'> = {
  id: 'run-123',
  title: 'CropScan: AI crop disease detection',
  industry: 'Agriculture / AgriTech',
  created_at: '2026-10-29T10:00:00.000+00:00',
  started_at: '2026-10-29T10:00:01.000+00:00',
  finished_at: null,
  duration_s: null,
  elapsed_s: 24.5,
  cancel_requested: false,
  message: null,
  submission: {
    idea_description: 'A mobile app that detects crop diseases from a photo of a leaf.',
    industry: 'Agriculture / AgriTech',
    target_customers: 'Small farmers in India',
    relevant_details: null,
  },
  idea_override: null,
};

/** Running, with the market stage in flight and a part-finished result. */
export const RUNNING: RunDetail = {
  ...BASE,
  state: 'running',
  stages: [
    stage('extraction', 'Understanding your idea', 'done', 6.5),
    stage('search', 'Searching the web', 'done', 18.2),
    stage('market_opportunity', 'Analysing the market', 'running', 12.1),
    stage('competitor_analysis', 'Comparing competitors', 'waiting'),
  ],
  result: null,
};

export const DONE: RunDetail = {
  ...BASE,
  state: 'done',
  finished_at: '2026-10-29T10:01:49.000+00:00',
  duration_s: 108.9,
  elapsed_s: 108.9,
  stages: [
    stage('extraction', 'Understanding your idea', 'done', 6.5),
    stage('search', 'Searching the web', 'done', 18.2),
    stage('market_opportunity', 'Analysing the market', 'done', 27.3),
    stage('competitor_analysis', 'Comparing competitors', 'done', 56.9),
  ],
  result: COMPLETE_RESULT,
};

export const PARTIAL: RunDetail = {
  ...DONE,
  message: 'Some parts could not be completed. What finished is shown below.',
  stages: [
    stage('extraction', 'Understanding your idea', 'done', 6.5),
    stage('search', 'Searching the web', 'done', 18.2),
    stage('market_opportunity', 'Analysing the market', 'done', 27.3),
    { ...stage('competitor_analysis', 'Comparing competitors', 'failed', 3.1), message: 'The AI service is busy right now.' },
  ],
  result: {
    ...COMPLETE_RESULT,
    status: 'partial',
    competitors: null,
    errors: [
      { stage: 'competitor_analysis', code: 'llm_api_error', message: 'The AI service is busy right now.' },
    ],
  },
};

export const FAILED: RunDetail = {
  ...BASE,
  state: 'failed',
  finished_at: '2026-10-29T10:00:05.000+00:00',
  duration_s: 4.2,
  elapsed_s: 4.2,
  message: 'The AI service is busy right now. Please try again in a minute.',
  stages: [
    { ...stage('extraction', 'Understanding your idea', 'failed', 4.2), message: 'The AI service is busy right now.' },
    stage('search', 'Searching the web', 'skipped'),
    stage('market_opportunity', 'Analysing the market', 'skipped'),
    stage('competitor_analysis', 'Comparing competitors', 'skipped'),
  ],
  result: null,
};

export const CANCELLED: RunDetail = {
  ...BASE,
  state: 'cancelled',
  finished_at: '2026-10-29T10:00:30.000+00:00',
  duration_s: 29.4,
  elapsed_s: 29.4,
  cancel_requested: true,
  message: 'Cancelled. What finished before the cancel is shown below.',
  stages: [
    stage('extraction', 'Understanding your idea', 'done', 6.5),
    stage('search', 'Searching the web', 'done', 18.2),
    stage('market_opportunity', 'Analysing the market', 'cancelled'),
    stage('competitor_analysis', 'Comparing competitors', 'cancelled'),
  ],
  result: { ...COMPLETE_RESULT, status: 'partial', market: null, competitors: null },
};

export const CANCEL_REQUESTED: RunDetail = { ...RUNNING, cancel_requested: true };
