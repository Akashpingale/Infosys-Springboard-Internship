/**
 * Watching one run (KIRO_UI_UPGRADE_SPEC.md Sections 8.2 and 8.3).
 *
 * GET /api/runs/{id} is polled every 1.5 s while the run is going and the polling stops as soon as
 * it reaches `done`, `failed` or `cancelled`, so a finished run costs no further requests. Polling
 * only reads; it can never start a second run.
 *
 * A lost connection does not throw the run away: TanStack Query keeps the last state it had, and
 * the page says it is retrying (Section 8.2).
 */

import { useMutation, useQuery, useQueryClient, type UseQueryResult } from '@tanstack/react-query';

import { request } from '@/api/client';
import { queryKeys } from '@/api/queries';
import type { components } from '@/api/types.gen';

export type RunDetail = components['schemas']['RunDetail'];
export type RunStage = components['schemas']['RunStage'];
export type RunState = RunDetail['state'];

export const POLL_INTERVAL_MS = 1500;
const ACTIVE: RunState[] = ['queued', 'running'];

export function isActive(state: RunState | undefined): boolean {
  return state !== undefined && ACTIVE.includes(state);
}

/** The run, re-read every 1.5 s until it ends. */
export function useRun(runId: string | undefined): UseQueryResult<RunDetail> {
  return useQuery({
    queryKey: queryKeys.run(runId ?? 'unknown'),
    queryFn: () => request<RunDetail>(`/api/runs/${encodeURIComponent(runId ?? '')}`),
    enabled: Boolean(runId),
    // Section 8.3: poll while it runs, stop on a terminal state.
    refetchInterval: (query) => (isActive(query.state.data?.state) ? POLL_INTERVAL_MS : false),
    refetchIntervalInBackground: false,
    staleTime: 0,
    // The run's own state is the thing being watched, so a stale snapshot is better than none.
    placeholderData: (previous) => previous,
  });
}

/** POST /api/runs/{id}/cancel. The backend stops before its next stage or outside call. */
export function useCancelRun(runId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => request<RunDetail>(`/api/runs/${encodeURIComponent(runId ?? '')}/cancel`, { method: 'POST' }),
    onSuccess: (detail) => {
      queryClient.setQueryData(queryKeys.run(detail.id), detail);
      void queryClient.invalidateQueries({ queryKey: queryKeys.runs });
    },
  });
}
