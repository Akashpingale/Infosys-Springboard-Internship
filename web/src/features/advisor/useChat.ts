import { useMutation, useQuery, useQueryClient, type UseMutationResult, type UseQueryResult } from '@tanstack/react-query';
import * as React from 'react';

import { request } from '@/api/client';
import { queryKeys } from '@/api/queries';
import type { components } from '@/api/types.gen';

export type ChatThread = components['schemas']['ChatThread'];
export type ChatMessage = components['schemas']['ChatMessage'];
export type ChatParagraph = components['schemas']['ChatParagraph'];
export type ChatReply = components['schemas']['ChatReply'];

export class ChatCancelled extends Error {
  constructor() {
    super('The question was cancelled.');
    this.name = 'ChatCancelled';
  }
}

export function isCancelled(error: unknown): error is ChatCancelled {
  return error instanceof ChatCancelled;
}

function chatPath(runId: string | undefined): string {
  return `/api/runs/${encodeURIComponent(runId ?? '')}/chat`;
}

export function useChatThread(runId: string | undefined, enabled = true): UseQueryResult<ChatThread> {
  return useQuery({
    queryKey: queryKeys.chat(runId ?? 'unknown'),
    queryFn: () => request<ChatThread>(chatPath(runId)),
    enabled: Boolean(runId) && enabled,
    staleTime: 0,
  });
}

export type SendChatResult = UseMutationResult<ChatReply, Error, string> & { cancel: () => void };

export function useSendChat(runId: string | undefined): SendChatResult {
  const queryClient = useQueryClient();
  const controller = React.useRef<AbortController | null>(null);
  const mutation = useMutation({
    mutationFn: async (message: string) => {
      const abort = new AbortController();
      controller.current = abort;
      try {
        return await request<ChatReply>(chatPath(runId), {
          method: 'POST',
          body: { message },
          signal: abort.signal,
        });
      } catch (error) {
        if (abort.signal.aborted) {
          throw new ChatCancelled();
        }
        throw error;
      } finally {
        if (controller.current === abort) {
          controller.current = null;
        }
      }
    },
    onSuccess: (reply) => {
      queryClient.setQueryData<ChatThread>(queryKeys.chat(runId ?? 'unknown'), (previous) =>
        previous ? { ...previous, remaining_turns: reply.remaining_turns } : previous,
      );
      void queryClient.invalidateQueries({ queryKey: queryKeys.chat(runId ?? 'unknown') });
    },
  });
  const cancel = React.useCallback(() => controller.current?.abort(), []);
  return { ...mutation, cancel };
}

export function useClearChat(runId: string | undefined): UseMutationResult<void, Error, void> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => request<void>(chatPath(runId), { method: 'DELETE' }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.chat(runId ?? 'unknown') });
    },
  });
}
