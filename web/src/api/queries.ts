/**
 * Query hooks over the typed client (KIRO_UI_UPGRADE_SPEC.md Sections 10.1 and 11).
 *
 * The run hooks that Prompts E to I need are added as those screens are built. What is here now is
 * what the shell itself uses: the backend's limits and the provider status.
 *
 * `MetaResponse` is taken from the generated OpenAPI types, so the front end cannot drift from the
 * backend's schema.
 */

import { useQuery, type UseQueryResult } from '@tanstack/react-query';

import { request } from '@/api/client';
import type { components } from '@/api/types.gen';

export type MetaResponse = components['schemas']['MetaResponse'];
export type RunSummary = components['schemas']['RunSummary'];
export type RunList = components['schemas']['RunList'];
export type HealthResponse = { status: string; llm_configured: boolean; search_configured: boolean };

export const queryKeys = {
  meta: ['meta'] as const,
  health: ['health'] as const,
  runs: ['runs'] as const,
  run: (id: string) => ['runs', id] as const,
  /** Milestone 3: a run's Advisor conversation. */
  chat: (id: string) => ['chat', id] as const,
};

/** The form limits, industries, examples, stage labels and provider status. */
export function useMeta(): UseQueryResult<MetaResponse> {
  return useQuery({
    queryKey: queryKeys.meta,
    queryFn: () => request<MetaResponse>('/api/meta'),
    // The limits change only when the backend is redeployed.
    staleTime: 5 * 60_000,
  });
}

/** Whether the backend is reachable, and which keys it has configured. Never a key itself. */
export function useHealth(): UseQueryResult<HealthResponse> {
  return useQuery({
    queryKey: queryKeys.health,
    queryFn: () => request<HealthResponse>('/health'),
  });
}

/**
 * The saved validations, newest first (Section 7.5).
 *
 * Read fresh each time the history is opened, because a run started in another tab, or one that
 * finished since, should show without a reload.
 */
export function useRuns(): UseQueryResult<RunSummary[]> {
  return useQuery({
    queryKey: queryKeys.runs,
    queryFn: async () => (await request<RunList>('/api/runs')).runs,
    staleTime: 0,
  });
}
