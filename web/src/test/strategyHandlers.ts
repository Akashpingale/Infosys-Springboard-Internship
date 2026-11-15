import { http, HttpResponse } from 'msw';

import { API_URL } from '@/api/client';
import type { MetaResponse } from '@/api/queries';
import type { ChatMessage, ChatReply, ChatThread } from '@/features/advisor/useChat';
import type { RunDetail, RunStage } from '@/features/run/useRun';
import type { PipelineResult } from '@/lib/results';
import { META } from '@/test/fixtures';
import { DONE } from '@/test/runFixtures';
import synthetic from '@/test/strategyFixture.synthetic.json';

export const SYNTHETIC_STRATEGY_RESULT = synthetic as unknown as PipelineResult;

export const META_WITH_STRATEGY: MetaResponse = {
  ...META,
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

export const STRATEGY_STAGE_LABELS = [
  ['swot_risk', 'Assessing strengths and risks'],
  ['mvp_recommendation', 'Recommending MVP features'],
  ['go_to_market', 'Planning go-to-market'],
] as const;

function strategyStage(key: string, label: string, status: RunStage['status'], elapsed?: number): RunStage {
  return {
    key,
    label,
    status,
    started_at: status === 'waiting' ? null : '2026-10-29T10:02:00.000+00:00',
    duration_s: elapsed ?? null,
    elapsed_s: elapsed ?? null,
    message: null,
  };
}

export function sevenStages(strategy: RunStage['status'][]): RunStage[] {
  return [
    ...DONE.stages,
    ...STRATEGY_STAGE_LABELS.map(([key, label], index) =>
      strategyStage(key, label, strategy[index] ?? 'waiting', strategy[index] === 'waiting' ? undefined : 9.5),
    ),
  ];
}

export const STRATEGY_RUNNING: RunDetail = {
  ...DONE,
  state: 'running',
  finished_at: null,
  duration_s: null,
  stages: sevenStages(['done', 'running', 'waiting']),
  constraints: SYNTHETIC_STRATEGY_RESULT.constraints ?? null,
};

export const STRATEGY_DONE: RunDetail = {
  ...DONE,
  stages: sevenStages(['done', 'done', 'done']),
  result: SYNTHETIC_STRATEGY_RESULT,
  constraints: SYNTHETIC_STRATEGY_RESULT.constraints ?? null,
};

export const USER_MESSAGE: ChatMessage = {
  id: 'msg-1',
  role: 'user',
  created_at: '2026-10-29T10:05:00.000+00:00',
  text: 'Which risk matters most?',
  paragraphs: [],
  follow_ups: [],
  status: 'ok',
  used_sections: [],
};

export const ASSISTANT_MESSAGE: ChatMessage = {
  id: 'msg-2',
  role: 'assistant',
  created_at: '2026-10-29T10:05:04.000+00:00',
  text: null,
  paragraphs: [
    {
      text: 'The synthetic register lists a competitor with a free app as the highest risk.',
      basis: 'ai_interpretation',
      sections: ['risks'],
      sources: [],
    },
  ],
  follow_ups: ['How could the MVP reduce that risk?'],
  status: 'ok',
  used_sections: ['risks'],
};

export const EMPTY_THREAD: ChatThread = {
  messages: [],
  suggestions: ['What is the biggest risk?', 'Which MVP feature comes first?'],
  available_sections: ['market', 'competitors', 'swot', 'risks', 'mvp', 'gtm'],
  remaining_turns: 25,
  limits: { max_message_chars: 1000, max_user_turns: 25 },
};

export function runUrl(id = 'run-123'): string {
  return `${API_URL}/api/runs/${id}`;
}

export function metaWithStrategy(meta: MetaResponse = META_WITH_STRATEGY) {
  return http.get(`${API_URL}/api/meta`, () => HttpResponse.json(meta));
}

export function strategyOk(capture?: (body: unknown) => void, id = 'run-123') {
  return http.post(`${runUrl(id)}/strategy`, async ({ request }) => {
    capture?.(await request.json());
    return HttpResponse.json({ run_id: id, state: 'queued' }, { status: 202 });
  });
}

export function chatThreadOk(thread: () => ChatThread, id = 'run-123') {
  return http.get(`${runUrl(id)}/chat`, () => HttpResponse.json(thread()));
}

export function chatAskOk(reply: ChatReply, capture?: (body: unknown) => void, id = 'run-123') {
  return http.post(`${runUrl(id)}/chat`, async ({ request }) => {
    capture?.(await request.json());
    return HttpResponse.json(reply);
  });
}

export function chatClearOk(capture?: () => void, id = 'run-123') {
  return http.delete(`${runUrl(id)}/chat`, () => {
    capture?.();
    return new HttpResponse(null, { status: 204 });
  });
}
