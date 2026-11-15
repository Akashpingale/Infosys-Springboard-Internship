/**
 * The mocked backend for the browser tests (KIRO_UI_UPGRADE_SPEC.md Prompt J).
 *
 * Every call the front end makes is answered here by route interception. Nothing reaches a server:
 * no validation is started, no provider is called and no API credit is spent. A request to an
 * address this file does not know about is failed on purpose, so a test cannot quietly depend on a
 * real backend being up.
 *
 * The bodies are the saved results the project already has, read as test data:
 * src/test/liveFintech.json is the 27 October fintech run and src/test/liveAgritech.json the
 * agritech one, both produced by the real pipeline. The partial, failed, cancelled and running
 * states are derived from them in the same shapes the backend returns.
 */

import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import type { Page, Route } from '@playwright/test';

/* The API base the front end is built against (src/api/client.ts). */
const API = 'http://127.0.0.1:8000';

type Json = Record<string, unknown>;

/*
 * Read rather than imported: Playwright's module loader wants an import attribute for JSON, and
 * reading the file keeps these fixtures the same bytes the unit tests use.
 */
const HERE = dirname(fileURLToPath(import.meta.url));

function saved(name: string): Json {
  return JSON.parse(readFileSync(join(HERE, '..', 'src', 'test', `${name}.json`), 'utf8')) as Json;
}

const FINTECH = saved('liveFintech');
const AGRITECH = saved('liveAgritech');
/*
 * Milestone 3: the synthetic strategy result the unit tests use (strategyFixture.synthetic.json),
 * an agritech result with a SWOT and risk review, an MVP plan and a go-to-market plan. It is
 * deliberately plain test data, never evidence.
 */
const STRATEGY = saved('strategyFixture.synthetic');

export const META: Json = {
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
  industries: [
    'Agriculture / AgriTech',
    'Healthcare / HealthTech',
    'Finance / FinTech',
    'Education / EdTech',
    'Food & Beverage',
    'Other',
  ],
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
  // Milestone 3 (plan 12.1): the strategy stages can run, with these constraint limits, and the
  // Advisor's limits.
  strategy: {
    available: true,
    time_limit_s: 150,
    constraints: {
      team_size: { min_value: 1, max_value: 10 },
      months_to_mvp: { min_value: 1, max_value: 12 },
      launch_region: { min_chars: null, max_chars: 60, min_words: null },
      budget_levels: ['bootstrapped', 'small', 'funded'],
      technical_skills: ['non_technical', 'some', 'strong'],
    },
  },
  chat: { max_message_chars: 1000, max_user_turns: 25 },
};

export const HEALTH: Json = { status: 'ok', llm_configured: true, search_configured: true };

function stage(key: string, label: string, status: string, seconds: number | null = null, message: string | null = null): Json {
  return {
    key,
    label,
    status,
    started_at: status === 'waiting' ? null : '2026-10-27T15:34:00.000+00:00',
    duration_s: seconds,
    elapsed_s: seconds,
    message,
  };
}

const STAGES_DONE = [
  stage('extraction', 'Understanding your idea', 'done', 13.9),
  stage('search', 'Searching the web', 'done', 14.7),
  stage('market_opportunity', 'Analysing the market', 'done', 26.4),
  stage('competitor_analysis', 'Comparing competitors', 'done', 47.4),
];

/* Milestone 3: the three strategy stages a run with strategy adds after the four above (plan 5.1). */
const STRATEGY_STAGES = [
  ['swot_risk', 'Assessing strengths and risks', 18.2],
  ['mvp_recommendation', 'Recommending MVP features', 21.6],
  ['go_to_market', 'Planning go-to-market', 19.3],
] as const;

/** The seven stages, the strategy ones in the given states (missing ones are waiting). */
function sevenStages(first: Json[], strategy: string[], messages: (string | null)[] = []): Json[] {
  return [
    ...first,
    ...STRATEGY_STAGES.map(([key, label, seconds], index) => {
      const status = strategy[index] ?? 'waiting';
      const elapsed = status === 'waiting' ? null : status === 'running' ? 6.4 : status === 'failed' ? 2.8 : seconds;
      return stage(key, label, status, elapsed, messages[index] ?? null);
    }),
  ];
}

const STRATEGY_BUSY = 'The AI service is busy right now.';

/**
 * The strategy result with some of its parts left out, as a run still going or a failed stage
 * leaves it. A failed part also leaves an error, and takes its own notices with it.
 */
function strategyResult(drop: ('swot' | 'mvp' | 'gtm')[], failed: string[] = []): Json {
  const result = { ...STRATEGY };
  for (const field of drop) {
    result[field] = null;
  }
  if (failed.length > 0) {
    result['status'] = 'partial';
    result['errors'] = failed.map((key) => ({ stage: key, code: 'llm_api_error', message: STRATEGY_BUSY }));
    result['notices'] = ((STRATEGY['notices'] as Json[]) ?? []).filter(
      (notice) => !failed.includes(notice['stage'] as string),
    );
  }
  return result;
}

const SUBMISSION: Json = {
  idea_description:
    'A platform that automatically reads bank and UPI statements for small businesses and forecasts their cash flow.',
  industry: 'Finance / FinTech',
  target_customers: 'Small business owners in Indian cities',
  relevant_details: null,
};

function detail(over: Json): Json {
  return {
    id: 'run-complete',
    title: 'Cash-flow and Expense Management Platform for Small Businesses',
    industry: 'Finance / FinTech',
    state: 'done',
    created_at: '2026-10-27T15:34:00.000+00:00',
    started_at: '2026-10-27T15:34:00.000+00:00',
    finished_at: '2026-10-27T15:35:42.000+00:00',
    duration_s: 102.486,
    elapsed_s: 102.486,
    cancel_requested: false,
    message: null,
    stages: STAGES_DONE,
    submission: SUBMISSION,
    idea_override: null,
    constraints: null,
    result: FINTECH['result'],
    ...over,
  };
}

/** The result with its competitor analysis missing, as a failed competitor stage leaves it. */
function partialResult(): Json {
  const result = { ...(FINTECH['result'] as Json) };
  result['status'] = 'partial';
  result['competitors'] = null;
  result['errors'] = [
    { stage: 'competitor_analysis', code: 'llm_api_error', message: 'The AI service is busy right now.' },
  ];
  return result;
}

/** Every run the browser tests can open, by id. */
export const RUNS: Record<string, Json> = {
  'run-complete': detail({}),

  'run-agritech': detail({
    id: 'run-agritech',
    title: 'CropScan: AI crop disease detection for small farmers',
    industry: 'Agriculture / AgriTech',
    duration_s: 159.2,
    result: AGRITECH['result'],
  }),

  'run-partial': detail({
    id: 'run-partial',
    title: 'Cash-flow platform, partial result',
    message: 'Some parts could not be completed. What finished is shown below.',
    duration_s: 58.1,
    stages: [
      ...STAGES_DONE.slice(0, 3),
      stage('competitor_analysis', 'Comparing competitors', 'failed', 3.1, 'The AI service is busy right now.'),
    ],
    result: partialResult(),
  }),

  'run-failed': detail({
    id: 'run-failed',
    title: 'Cash-flow platform, failed run',
    state: 'failed',
    message: 'The AI service is busy right now. Please try again in a minute.',
    duration_s: 4.2,
    stages: [
      stage('extraction', 'Understanding your idea', 'failed', 4.2, 'The AI service is busy right now.'),
      stage('search', 'Searching the web', 'skipped'),
      stage('market_opportunity', 'Analysing the market', 'skipped'),
      stage('competitor_analysis', 'Comparing competitors', 'skipped'),
    ],
    result: null,
  }),

  'run-cancelled': detail({
    id: 'run-cancelled',
    title: 'Cash-flow platform, cancelled run',
    state: 'cancelled',
    message: 'Cancelled. What finished before the cancel is shown below.',
    duration_s: 29.4,
    cancel_requested: true,
    stages: [
      ...STAGES_DONE.slice(0, 2),
      stage('market_opportunity', 'Analysing the market', 'cancelled'),
      stage('competitor_analysis', 'Comparing competitors', 'cancelled'),
    ],
    result: null,
  }),

  'run-running': detail({
    id: 'run-running',
    title: 'Cash-flow and Expense Management Platform for Small Businesses',
    state: 'running',
    finished_at: null,
    duration_s: null,
    elapsed_s: 41.2,
    stages: [
      ...STAGES_DONE.slice(0, 2),
      stage('market_opportunity', 'Analysing the market', 'running', 12.1),
      stage('competitor_analysis', 'Comparing competitors', 'waiting'),
    ],
    result: null,
  }),

  /* Milestone 3: runs with strategy, from the synthetic strategy result. */
  'run-strategy': detail({
    id: 'run-strategy',
    title: 'CropScan: AI crop disease detection',
    industry: 'Agriculture / AgriTech',
    duration_s: 161.0,
    elapsed_s: 161.0,
    stages: sevenStages(STAGES_DONE, ['done', 'done', 'done']),
    constraints: STRATEGY['constraints'],
    result: STRATEGY,
  }),

  'run-strategy-progress': detail({
    id: 'run-strategy-progress',
    title: 'CropScan: AI crop disease detection',
    industry: 'Agriculture / AgriTech',
    state: 'running',
    finished_at: null,
    duration_s: null,
    elapsed_s: 41.2,
    stages: sevenStages(
      [...STAGES_DONE.slice(0, 2), stage('market_opportunity', 'Analysing the market', 'running', 12.1),
        stage('competitor_analysis', 'Comparing competitors', 'waiting')],
      [],
    ),
    constraints: STRATEGY['constraints'],
    result: null,
  }),

  'run-strategy-running': detail({
    id: 'run-strategy-running',
    title: 'CropScan: AI crop disease detection',
    industry: 'Agriculture / AgriTech',
    state: 'running',
    finished_at: null,
    duration_s: null,
    elapsed_s: 127.0,
    stages: sevenStages(STAGES_DONE, ['done', 'running']),
    constraints: STRATEGY['constraints'],
    result: strategyResult(['mvp', 'gtm']),
  }),

  'run-strategy-partial': detail({
    id: 'run-strategy-partial',
    title: 'CropScan, strategy partly generated',
    industry: 'Agriculture / AgriTech',
    message: 'Some parts could not be completed. What finished is shown below.',
    duration_s: 144.5,
    elapsed_s: 144.5,
    stages: sevenStages(STAGES_DONE, ['done', 'done', 'failed'], [null, null, STRATEGY_BUSY]),
    constraints: STRATEGY['constraints'],
    result: strategyResult(['gtm'], ['go_to_market']),
  }),

  'run-strategy-failed': detail({
    id: 'run-strategy-failed',
    title: 'CropScan, strategy not generated',
    industry: 'Agriculture / AgriTech',
    message: 'Some parts could not be completed. What finished is shown below.',
    duration_s: 110.9,
    elapsed_s: 110.9,
    stages: sevenStages(STAGES_DONE, ['failed', 'failed', 'failed'], [STRATEGY_BUSY, STRATEGY_BUSY, STRATEGY_BUSY]),
    constraints: null,
    result: strategyResult(['swot', 'mvp', 'gtm'], ['swot_risk', 'mvp_recommendation', 'go_to_market']),
  }),
};

/* Milestone 3: the Advisor's conversation (GET /api/runs/{id}/chat), plan 11 and 14.6. */
const QUESTION = 'Which risk should I deal with first, and how could I reduce it?';
const SECOND_QUESTION = 'How could the MVP reduce that risk?';

const STRATEGY_SECTIONS = ['market', 'competitors', 'swot', 'risks', 'mvp', 'gtm'];

function userMessage(id: string, text: string, at: string): Json {
  return { id, role: 'user', created_at: at, text, paragraphs: [], follow_ups: [], status: 'ok', used_sections: [] };
}

function advisorMessage(id: string, at: string, paragraphs: Json[], followUps: string[]): Json {
  const sections = [...new Set(paragraphs.flatMap((paragraph) => paragraph['sections'] as string[]))];
  return { id, role: 'assistant', created_at: at, text: null, paragraphs, follow_ups: followUps, status: 'ok', used_sections: sections };
}

export const CONVERSATION: Json[] = [
  userMessage('msg-1', QUESTION, '2026-10-29T10:05:00.000+00:00'),
  advisorMessage(
    'msg-2',
    '2026-10-29T10:05:04.000+00:00',
    [
      {
        text: 'Start with "Farmers stay with the free app". It is rated high, and the competitor analysis lists free diagnosis apps that farmers already use.',
        basis: 'sourced',
        sections: ['risks', 'competitors'],
        sources: [
          { analysis: 'competitors', id: 'S1' },
          { analysis: 'competitors', id: 'S5' },
        ],
      },
      {
        text: 'Pairing each diagnosis with treatment advice in the farmer\u2019s language is the planned way to stand apart. That is an AI interpretation of your results, not a finding.',
        basis: 'ai_interpretation',
        sections: ['mvp', 'gtm'],
        sources: [],
      },
    ],
    [SECOND_QUESTION, 'Which channel reaches cooperatives first?'],
  ),
  userMessage('msg-3', SECOND_QUESTION, '2026-10-29T10:06:10.000+00:00'),
  advisorMessage(
    'msg-4',
    '2026-10-29T10:06:15.000+00:00',
    [
      {
        text: 'The first release includes "Photo-based diagnosis" and "Treatment advice", which the plan links to that risk. "Local language support" is also in the first release.',
        basis: 'ai_interpretation',
        sections: ['mvp', 'risks'],
        sources: [],
      },
    ],
    ['What is the first experiment for the top channel?'],
  ),
];

/** The thread a run's Advisor opens on: empty, with the starter questions. */
function chatThread(id: string): Json {
  const result = RUNS[id]?.['result'] as Json | null | undefined;
  const strategy = Boolean(result?.['swot'] || result?.['mvp'] || result?.['gtm']);
  return {
    messages: [],
    suggestions: strategy
      ? [
          'Which risk should I deal with first?',
          'Why are these features in the first release?',
          'Which channel should I start with?',
          'Which competitor is closest to my idea?',
        ]
      : ['Which competitor is closest to my idea?', 'How big is the market for my priority segment?'],
    available_sections: strategy ? STRATEGY_SECTIONS : ['market', 'competitors'],
    remaining_turns: 25,
    limits: { max_message_chars: 1000, max_user_turns: 25 },
  };
}

/** The thread with the conversation above in it. */
export function conversationThread(id = 'run-strategy'): Json {
  return { ...chatThread(id), messages: CONVERSATION, remaining_turns: 23 };
}

/**
 * A full conversation. The turn limit is lowered to two here, a setting the backend allows
 * (CHAT_MAX_USER_TURNS), so the screen shows the full state without fifty messages.
 */
export function fullThread(id = 'run-strategy'): Json {
  return {
    ...chatThread(id),
    messages: CONVERSATION,
    remaining_turns: 0,
    limits: { max_message_chars: 1000, max_user_turns: 2 },
  };
}

/** The answer POST /api/runs/{id}/chat gives when the Advisor is asked to answer. */
export const REPLY: Json = {
  message: advisorMessage(
    'msg-reply',
    '2026-10-29T10:07:00.000+00:00',
    [
      {
        text: 'The register rates "Farmers stay with the free app" highest. That is an AI interpretation of your results.',
        basis: 'ai_interpretation',
        sections: ['risks'],
        sources: [],
      },
    ],
    [SECOND_QUESTION],
  ),
  remaining_turns: 24,
};

export const HISTORY: Json = {
  runs: [
    {
      id: 'run-complete',
      title: 'Cash-flow and Expense Management Platform for Small Businesses',
      industry: 'Finance / FinTech',
      state: 'done',
      status: 'complete',
      created_at: '2026-10-27T15:34:00.000+00:00',
      duration_s: 102.486,
    },
    {
      id: 'run-agritech',
      title: 'CropScan: AI crop disease detection for small farmers',
      industry: 'Agriculture / AgriTech',
      state: 'done',
      status: 'partial',
      created_at: '2026-10-26T09:10:00.000+00:00',
      duration_s: 159.2,
    },
    {
      id: 'run-running',
      title: 'Food surplus marketplace for restaurants',
      industry: 'Food & Beverage',
      state: 'running',
      status: null,
      created_at: '2026-10-28T08:00:00.000+00:00',
      duration_s: null,
    },
  ],
};

const REPORT = `# Startup idea validation report\n\nStatus: Complete\n\nThis is the saved report text.\n`;

export interface MockOptions {
  /** Replaces the history list, for the empty state. */
  history?: Json;
  /** Answers /api/meta and /health with a connection failure, for the offline state. */
  offline?: boolean;
  /** Never answers these paths, so the screen stays in its loading state. */
  hang?: string[];
  /** Milestone 3: the Advisor's conversation, instead of the empty one with starter questions. */
  thread?: Json;
  /**
   * Milestone 3: what a question to the Advisor gets. An answer (the default), no answer at all so
   * it stays pending, or the AI service failing.
   */
  ask?: 'answer' | 'hang' | 'fail';
}

function json(route: Route, body: unknown, status = 200): Promise<void> {
  return route.fulfill({
    status,
    contentType: 'application/json',
    headers: { 'Access-Control-Allow-Origin': '*' },
    body: JSON.stringify(body),
  });
}

function error(route: Route, code: string, message: string, status: number): Promise<void> {
  return json(route, { error: { code, message } }, status);
}

/**
 * Answer every backend call for one page.
 *
 * Returns the list of addresses that were asked for, so a test can assert that nothing unexpected
 * was called: starting a run, for instance, must never happen in these tests.
 */
export async function mockApi(page: Page, options: MockOptions = {}): Promise<string[]> {
  const asked: string[] = [];

  await page.route(`${API}/**`, async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname;
    const method = route.request().method();
    asked.push(`${method} ${path}`);

    if (options.hang?.some((prefix) => path.startsWith(prefix))) {
      // Left unanswered on purpose: the screen stays as it looks while waiting.
      return;
    }

    if (options.offline) {
      return route.abort('connectionrefused');
    }

    if (method === 'OPTIONS') {
      return route.fulfill({
        status: 204,
        headers: {
          'Access-Control-Allow-Origin': '*',
          'Access-Control-Allow-Methods': 'GET,POST,PATCH,DELETE,OPTIONS',
          'Access-Control-Allow-Headers': 'Content-Type',
        },
      });
    }

    if (path === '/health') {
      return json(route, HEALTH);
    }
    if (path === '/api/meta') {
      return json(route, META);
    }
    if (path === '/api/runs' && method === 'GET') {
      return json(route, options.history ?? HISTORY);
    }

    const report = path.match(/^\/api\/runs\/([^/]+)\/report\.md$/);
    if (report) {
      return route.fulfill({
        status: 200,
        contentType: 'text/markdown; charset=utf-8',
        headers: { 'Access-Control-Allow-Origin': '*' },
        body: REPORT,
      });
    }

    /*
     * Milestone 3: the Advisor's conversation, and generating strategy for a saved run. Both are
     * answered without any model being called.
     */
    const chat = path.match(/^\/api\/runs\/([^/]+)\/chat$/);
    if (chat) {
      const id = chat[1] ?? '';
      if (!RUNS[id]) {
        return error(route, 'run_not_found', 'This validation could not be found. It may have been deleted.', 404);
      }
      if (method === 'DELETE') {
        return route.fulfill({ status: 204, headers: { 'Access-Control-Allow-Origin': '*' } });
      }
      if (method === 'POST') {
        if (options.ask === 'hang') {
          // Left unanswered on purpose: the question stays pending.
          return;
        }
        if (options.ask === 'fail') {
          return error(route, 'llm_api_error', 'The AI service is not responding. Please try again.', 502);
        }
        return json(route, REPLY);
      }
      return json(route, options.thread ?? chatThread(id));
    }

    const strategy = path.match(/^\/api\/runs\/([^/]+)\/strategy$/);
    if (strategy && method === 'POST') {
      return json(route, { run_id: strategy[1] ?? '', state: 'queued' }, 202);
    }

    const one = path.match(/^\/api\/runs\/([^/]+)$/);
    if (one) {
      const id = one[1] ?? '';
      if (method === 'DELETE') {
        return route.fulfill({ status: 204, headers: { 'Access-Control-Allow-Origin': '*' } });
      }
      if (method === 'PATCH') {
        const body = JSON.parse(route.request().postData() ?? '{}') as { title?: string };
        const run = RUNS[id];
        return json(route, {
          id,
          title: body.title ?? '',
          industry: (run?.['industry'] as string) ?? 'Other',
          state: 'done',
          status: 'complete',
          created_at: '2026-10-27T15:34:00.000+00:00',
          duration_s: 102.486,
        });
      }
      const run = RUNS[id];
      return run
        ? json(route, run)
        : error(route, 'run_not_found', 'This validation could not be found. It may have been deleted.', 404);
    }

    /*
     * Extraction is answered so the review step can be reached; starting a run is refused loudly,
     * because no browser test should ever ask for one.
     */
    if (path === '/api/ideas/extract' && method === 'POST') {
      return json(route, {
        idea_title: 'Cash-flow platform for small businesses',
        problem: 'Small business owners lose track of cash flow across bank and UPI accounts.',
        solution: 'A platform that reads their statements and forecasts the weeks ahead.',
        target_customers: ['Small business owners in Indian cities', 'Shopkeepers'],
        industry: 'Finance / FinTech',
        key_features: ['Bank statement reading', 'UPI statement reading', 'Weekly cash flow forecast'],
      });
    }
    if (path === '/api/runs' && method === 'POST') {
      throw new Error('A browser test tried to start a validation. These tests must never do that.');
    }

    return error(route, 'not_mocked', `No mock for ${method} ${path}`, 501);
  });

  return asked;
}
