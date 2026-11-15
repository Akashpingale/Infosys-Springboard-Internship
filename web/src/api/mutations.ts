/**
 * The two calls the submission flow makes (KIRO_UI_UPGRADE_SPEC.md Sections 7.1, 7.2 and 10.1).
 *
 * Extraction is its own step, so the founder reviews the structured idea before the expensive
 * stages run; starting the run then sends that reviewed idea as `idea_override`, and the backend
 * skips extracting it again.
 */

import { useMutation, useQueryClient, type UseMutationResult } from '@tanstack/react-query';

import { request } from '@/api/client';
import { queryKeys, type RunSummary } from '@/api/queries';
import type { components } from '@/api/types.gen';

export type IdeaSubmission = components['schemas']['IdeaSubmission'];
export type ExtractedIdea = components['schemas']['ExtractedIdea'];
export type RunStarted = components['schemas']['RunStarted'];

/** POST /api/ideas/extract: the founder's text becomes a structured idea. About six seconds. */
export function useExtractIdea(): UseMutationResult<ExtractedIdea, Error, IdeaSubmission> {
  return useMutation({
    mutationFn: (submission: IdeaSubmission) =>
      request<ExtractedIdea>('/api/ideas/extract', { method: 'POST', body: submission }),
  });
}

export interface StartRunInput {
  submission: IdeaSubmission;
  /** The idea as the founder left it after the review step. */
  idea_override?: ExtractedIdea;
  /** Milestone 3: run the three strategy stages after the analysis. */
  include_strategy?: boolean;
  /** Only the resources the founder filled in; left out when none was. */
  constraints?: components['schemas']['StrategyConstraints'];
}

/** POST /api/runs: the full pipeline starts in the background and answers with a run id. */
export function useStartRun(): UseMutationResult<RunStarted, Error, StartRunInput> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: StartRunInput) => request<RunStarted>('/api/runs', { method: 'POST', body: input }),
    onSuccess: () => {
      // The history gained a row, so its list is no longer current.
      void queryClient.invalidateQueries({ queryKey: queryKeys.runs });
    },
  });
}

export interface RenameRunInput {
  id: string;
  title: string;
}

/** PATCH /api/runs/{id}: rename a saved validation. Only the title changes. */
export function useRenameRun(): UseMutationResult<RunSummary, Error, RenameRunInput> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, title }: RenameRunInput) =>
      request<RunSummary>(`/api/runs/${encodeURIComponent(id)}`, { method: 'PATCH', body: { title } }),
    onSuccess: (summary) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.runs });
      void queryClient.invalidateQueries({ queryKey: queryKeys.run(summary.id) });
    },
  });
}

/** DELETE /api/runs/{id}. The backend refuses while the run is still going (409). */
export function useDeleteRun(): UseMutationResult<void, Error, string> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => request<void>(`/api/runs/${encodeURIComponent(id)}`, { method: 'DELETE' }),
    onSuccess: (_result, id) => {
      // The run is gone, so its cached detail must not be served to the page again.
      queryClient.removeQueries({ queryKey: queryKeys.run(id) });
      void queryClient.invalidateQueries({ queryKey: queryKeys.runs });
    },
  });
}
