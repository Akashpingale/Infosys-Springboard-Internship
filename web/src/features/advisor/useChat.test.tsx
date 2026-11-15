import { transferableAbortController } from 'node:util';

import { act, renderHook, waitFor } from '@testing-library/react';
import { delay, http, HttpResponse } from 'msw';
import type * as React from 'react';
import { afterAll, beforeAll, describe, expect, it, vi } from 'vitest';

import { ApiError } from '@/api/client';
import { Providers } from '@/app/providers';
import { isCancelled, useChatThread, useClearChat, useSendChat, type ChatThread } from '@/features/advisor/useChat';
import { testQueryClient } from '@/test/render';
import { server } from '@/test/server';
import {
  ASSISTANT_MESSAGE,
  EMPTY_THREAD,
  USER_MESSAGE,
  chatAskOk,
  chatClearOk,
  chatThreadOk,
  runUrl,
} from '@/test/strategyHandlers';

beforeAll(() => {
  vi.stubGlobal('AbortController', transferableAbortController().constructor);
});

afterAll(() => {
  vi.unstubAllGlobals();
});

function wrapper() {
  const client = testQueryClient();
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <Providers client={client}>{children}</Providers>;
  };
}

function useBoth(runId: string) {
  return { thread: useChatThread(runId), send: useSendChat(runId), clear: useClearChat(runId) };
}

describe('Chat thread', () => {
  it('reads the saved conversation', async () => {
    server.use(chatThreadOk(() => EMPTY_THREAD));
    const { result } = renderHook(() => useChatThread('run-123'), { wrapper: wrapper() });

    await waitFor(() => expect(result.current.data).toEqual(EMPTY_THREAD));
  });

  it('asks nothing while it is not enabled', async () => {
    let reads = 0;
    server.use(
      chatThreadOk(() => {
        reads += 1;
        return EMPTY_THREAD;
      }),
    );
    const { result } = renderHook(() => useChatThread('run-123', false), { wrapper: wrapper() });

    await new Promise((resolve) => setTimeout(resolve, 100));
    expect(reads).toBe(0);
    expect(result.current.fetchStatus).toBe('idle');
  });

  it("passes on the backend's reason when the conversation is not open yet", async () => {
    server.use(
      http.get(`${runUrl()}/chat`, () =>
        HttpResponse.json(
          { error: { code: 'chat_unavailable', message: 'Questions open once the validation has finished.' } },
          { status: 409 },
        ),
      ),
    );
    const { result } = renderHook(() => useChatThread('run-123'), { wrapper: wrapper() });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error).toBeInstanceOf(ApiError);
    expect((result.current.error as ApiError).code).toBe('chat_unavailable');
  });
});

describe('Sending a question', () => {
  it('posts the question alone, then reads the thread again', async () => {
    const sent: unknown[] = [];
    let thread: ChatThread = EMPTY_THREAD;
    server.use(
      chatThreadOk(() => thread),
      chatAskOk({ message: ASSISTANT_MESSAGE, remaining_turns: 24 }, (body) => {
        sent.push(body);
        thread = { ...EMPTY_THREAD, messages: [USER_MESSAGE, ASSISTANT_MESSAGE], remaining_turns: 24 };
      }),
    );
    const { result } = renderHook(() => useBoth('run-123'), { wrapper: wrapper() });
    await waitFor(() => expect(result.current.thread.data?.messages).toEqual([]));

    let reply: unknown;
    await act(async () => {
      reply = await result.current.send.mutateAsync('Which risk matters most?');
    });

    expect(sent).toEqual([{ message: 'Which risk matters most?' }]);
    expect(reply).toEqual({ message: ASSISTANT_MESSAGE, remaining_turns: 24 });
    await waitFor(() => expect(result.current.thread.data?.messages).toEqual([USER_MESSAGE, ASSISTANT_MESSAGE]));
    expect(result.current.thread.data?.remaining_turns).toBe(24);
  });

  it('can be cancelled while it waits, and says so rather than reporting a lost connection', async () => {
    let answered = false;
    server.use(
      chatThreadOk(() => EMPTY_THREAD),
      http.post(`${runUrl()}/chat`, async () => {
        await delay('infinite');
        answered = true;
        return HttpResponse.json({ message: ASSISTANT_MESSAGE, remaining_turns: 24 });
      }),
    );
    const { result } = renderHook(() => useBoth('run-123'), { wrapper: wrapper() });

    act(() => {
      result.current.send.mutate('Which risk matters most?');
    });
    await waitFor(() => expect(result.current.send.isPending).toBe(true));
    act(() => result.current.send.cancel());

    await waitFor(() => expect(result.current.send.isError).toBe(true));
    expect(isCancelled(result.current.send.error)).toBe(true);
    expect(result.current.send.error).not.toBeInstanceOf(ApiError);
    expect(answered).toBe(false);
  });

  it("keeps the backend's code for a refused question", async () => {
    server.use(
      http.post(`${runUrl()}/chat`, () =>
        HttpResponse.json(
          { error: { code: 'chat_cooldown', message: 'Wait a moment before the next question.' } },
          { status: 429 },
        ),
      ),
    );
    const { result } = renderHook(() => useSendChat('run-123'), { wrapper: wrapper() });

    act(() => {
      result.current.mutate('Again?');
    });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(isCancelled(result.current.error)).toBe(false);
    expect((result.current.error as ApiError).code).toBe('chat_cooldown');
    expect((result.current.error as ApiError).status).toBe(429);
  });

  it('does nothing when cancel is pressed with no question in flight', () => {
    const { result } = renderHook(() => useSendChat('run-123'), { wrapper: wrapper() });

    expect(() => result.current.cancel()).not.toThrow();
    expect(result.current.isIdle).toBe(true);
  });
});

describe('Clearing the conversation', () => {
  it('sends a delete, then reads the empty thread', async () => {
    let cleared = 0;
    let thread: ChatThread = { ...EMPTY_THREAD, messages: [USER_MESSAGE, ASSISTANT_MESSAGE], remaining_turns: 24 };
    server.use(
      chatThreadOk(() => thread),
      chatClearOk(() => {
        cleared += 1;
        thread = EMPTY_THREAD;
      }),
    );
    const { result } = renderHook(() => useBoth('run-123'), { wrapper: wrapper() });
    await waitFor(() => expect(result.current.thread.data?.messages).toHaveLength(2));

    await act(async () => {
      await result.current.clear.mutateAsync();
    });

    expect(cleared).toBe(1);
    await waitFor(() => expect(result.current.thread.data?.messages).toEqual([]));
    expect(result.current.thread.data?.remaining_turns).toBe(25);
  });
});
