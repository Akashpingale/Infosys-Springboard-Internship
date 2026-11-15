import { transferableAbortController } from 'node:util';

import { fireEvent, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { delay, http, HttpResponse } from 'msw';
import { afterAll, beforeAll, describe, expect, it, vi } from 'vitest';

import { AdvisorTab, type AdvisorTabProps } from '@/features/advisor/AdvisorTab';
import type { ChatMessage, ChatThread } from '@/features/advisor/useChat';
import type { RunDetail } from '@/features/run/useRun';
import { buildSourceIndex } from '@/lib/results';
import { renderWithApp } from '@/test/render';
import { server } from '@/test/server';
import {
  ASSISTANT_MESSAGE,
  EMPTY_THREAD,
  STRATEGY_DONE,
  USER_MESSAGE,
  chatAskOk,
  chatClearOk,
  chatThreadOk,
  metaWithStrategy,
  runUrl,
  strategyOk,
} from '@/test/strategyHandlers';

beforeAll(() => {
  vi.stubGlobal('AbortController', transferableAbortController().constructor);
});

afterAll(() => {
  vi.unstubAllGlobals();
});

const QUESTION = 'Which risk matters most?';

const SOURCED_REPLY: ChatMessage = {
  id: 'msg-4',
  role: 'assistant',
  created_at: '2026-10-29T10:06:00.000+00:00',
  text: null,
  paragraphs: [
    {
      text: 'The market report names crop AI as a growing market.',
      basis: 'sourced',
      sections: ['market', 'competitors'],
      sources: [
        { analysis: 'market', id: 'S1' },
        { analysis: 'competitors', id: 'S1' },
      ],
    },
    {
      text: 'This is a guess about the second season.',
      basis: 'assumption',
      sections: ['general'],
      sources: [],
    },
  ],
  follow_ups: ['Which segment should I reach first?', 'What should I verify next?'],
  status: 'ok',
  used_sections: ['market', 'competitors'],
};

function thread(overrides: Partial<ChatThread> = {}): ChatThread {
  return { ...EMPTY_THREAD, ...overrides };
}

let mounted: HTMLElement = document.body;

function renderTab(run: RunDetail = STRATEGY_DONE, props: Partial<AdvisorTabProps> = {}) {
  const result = run.result ?? null;
  const sources = result ? buildSourceIndex(result) : new Map();
  const opened: string[] = [];
  const view = renderWithApp(
    <AdvisorTab run={run} result={result} sources={sources} onOpenSource={(key) => opened.push(key)} {...props} />,
  );
  mounted = view.container.firstElementChild as HTMLElement;
  return { opened, sources, view };
}

function composer(): HTMLTextAreaElement {
  return screen.getByRole('textbox', { name: 'Your question' }) as HTMLTextAreaElement;
}

function live(): Element | null {
  return mounted.querySelector('[aria-live="polite"]');
}

describe('Advisor: header and starter questions', () => {
  it('names the tab, says what the answers rest on and lists the sections it can use', async () => {
    server.use(metaWithStrategy(), chatThreadOk(() => thread()));
    renderTab();

    expect(await screen.findByRole('heading', { name: 'Ask about this validation' })).toBeInTheDocument();
    expect(
      screen.getByText("Answers use only this validation's results. They can be wrong. Check important points against the sources."),
    ).toBeInTheDocument();
    const uses = await screen.findByRole('list', { name: 'The Advisor can use:' });
    expect(within(uses).getAllByRole('listitem').map((item) => item.textContent)).toEqual([
      'Market',
      'Competitors',
      'SWOT',
      'Risks',
      'MVP plan',
      'Go-to-market',
    ]);
  });

  it('offers the starter questions as buttons while the thread is empty', async () => {
    server.use(metaWithStrategy(), chatThreadOk(() => thread()));
    renderTab();

    expect(await screen.findByText('Ask about your market, competitors, risks, MVP or launch plan.')).toBeInTheDocument();
    const list = screen.getByRole('list', { name: 'Suggested questions' });
    expect(within(list).getAllByRole('button').map((button) => button.textContent)).toEqual([
      'What is the biggest risk?',
      'Which MVP feature comes first?',
    ]);
    expect(screen.queryByRole('list', { name: 'Conversation' })).not.toBeInTheDocument();
  });

  it('asks a starter question when it is pressed, then shows the answer', async () => {
    const sent: unknown[] = [];
    let current = thread();
    server.use(
      metaWithStrategy(),
      chatThreadOk(() => current),
      chatAskOk({ message: ASSISTANT_MESSAGE, remaining_turns: 24 }, (body) => {
        sent.push(body);
        current = thread({ messages: [{ ...USER_MESSAGE, text: 'What is the biggest risk?' }, ASSISTANT_MESSAGE], remaining_turns: 24 });
      }),
    );
    const user = userEvent.setup();
    renderTab();

    await user.click(await screen.findByRole('button', { name: 'What is the biggest risk?' }));

    await waitFor(() => expect(sent).toEqual([{ message: 'What is the biggest risk?' }]));
    expect(await screen.findByText(ASSISTANT_MESSAGE.paragraphs![0]!.text)).toBeInTheDocument();
    expect(screen.queryByRole('list', { name: 'Suggested questions' })).not.toBeInTheDocument();
    expect(composer()).toHaveFocus();
  });

  it('shows no suggestions once the thread has messages', async () => {
    server.use(metaWithStrategy(), chatThreadOk(() => thread({ messages: [USER_MESSAGE, ASSISTANT_MESSAGE] })));
    renderTab();

    expect(await screen.findByRole('list', { name: 'Conversation' })).toBeInTheDocument();
    expect(screen.queryByRole('list', { name: 'Suggested questions' })).not.toBeInTheDocument();
    expect(screen.queryByText('Ask about your market, competitors, risks, MVP or launch plan.')).not.toBeInTheDocument();
  });
});

describe('Advisor: the thread', () => {
  it('shows the saved conversation in order, yours on the right and the advisor on the left', async () => {
    server.use(metaWithStrategy(), chatThreadOk(() => thread({ messages: [USER_MESSAGE, ASSISTANT_MESSAGE] })));
    renderTab();

    const list = await screen.findByRole('list', { name: 'Conversation' });
    const items = within(list).getAllByRole('listitem');
    expect(items).toHaveLength(2);
    expect(items[0]).toHaveTextContent(`You${QUESTION}`);
    expect(items[0]).toHaveClass('justify-end');
    expect(items[1]).toHaveTextContent('Advisor');
    expect(items[1]).toHaveTextContent(ASSISTANT_MESSAGE.paragraphs![0]!.text);
    expect(items[1]).not.toHaveClass('justify-end');
  });

  it('gives every advisor paragraph a basis chip, its citation chips and where it came from', async () => {
    server.use(metaWithStrategy(), chatThreadOk(() => thread({ messages: [USER_MESSAGE, SOURCED_REPLY] })));
    const { opened, sources } = renderTab();

    const list = await screen.findByRole('list', { name: 'Conversation' });
    const reply = within(list).getAllByRole('listitem')[1]!;
    expect(within(reply).getByText('Sourced')).toBeInTheDocument();
    expect(within(reply).getByText('Assumption')).toBeInTheDocument();
    expect(within(reply).getByText('From: Market, Competitors')).toBeInTheDocument();
    expect(within(reply).queryByText(/From: General/)).not.toBeInTheDocument();

    const market = sources.get('market:S1')!;
    const competitor = sources.get('competitors:S1')!;
    expect(within(reply).getAllByRole('button', { name: /Open the source details/ }).map((chip) => chip.textContent)).toEqual([
      String(market.number),
      String(competitor.number),
    ]);
    await userEvent.setup().click(
      within(reply).getByRole('button', { name: `Source ${competitor.number}: ${competitor.title}. Open the source details.` }),
    );
    expect(opened).toEqual(['competitors:S1']);
  });

  it('shows the follow-up questions after the last advisor message, and asks one when it is pressed', async () => {
    const sent: unknown[] = [];
    server.use(
      metaWithStrategy(),
      chatThreadOk(() => thread({ messages: [USER_MESSAGE, SOURCED_REPLY], remaining_turns: 24 })),
      chatAskOk({ message: ASSISTANT_MESSAGE, remaining_turns: 23 }, (body) => sent.push(body)),
    );
    const user = userEvent.setup();
    renderTab();

    const list = await screen.findByRole('list', { name: 'Follow-up questions' });
    expect(within(list).getAllByRole('button').map((button) => button.textContent)).toEqual(SOURCED_REPLY.follow_ups);

    await user.click(within(list).getByRole('button', { name: 'What should I verify next?' }));
    await waitFor(() => expect(sent).toEqual([{ message: 'What should I verify next?' }]));
  });

  it('renders what the advisor wrote as text, never as markup', async () => {
    const markup: ChatMessage = {
      ...ASSISTANT_MESSAGE,
      paragraphs: [{ text: '<b>bold</b> <img src=x onerror=alert(1)>', basis: 'assumption', sections: [], sources: [] }],
    };
    server.use(metaWithStrategy(), chatThreadOk(() => thread({ messages: [{ ...USER_MESSAGE, text: '<i>mine</i>' }, markup] })));
    const { view } = renderTab();

    expect(await screen.findByText('<b>bold</b> <img src=x onerror=alert(1)>')).toBeInTheDocument();
    expect(screen.getByText('<i>mine</i>')).toBeInTheDocument();
    expect(view.container.querySelector('b, i, img')).toBeNull();
  });
});

describe('Advisor: asking', () => {
  it('sends the question, clears the composer, shows the answer and reads the thread again', async () => {
    const sent: unknown[] = [];
    let reads = 0;
    let current = thread();
    server.use(
      metaWithStrategy(),
      chatThreadOk(() => {
        reads += 1;
        return current;
      }),
      chatAskOk({ message: SOURCED_REPLY, remaining_turns: 24 }, (body) => {
        sent.push(body);
        current = thread({ messages: [USER_MESSAGE, SOURCED_REPLY], remaining_turns: 24 });
      }),
    );
    const user = userEvent.setup();
    renderTab();

    await user.type(await screen.findByRole('textbox', { name: 'Your question' }), `  ${QUESTION} `);
    await user.click(screen.getByRole('button', { name: 'Send' }));

    await waitFor(() => expect(sent).toEqual([{ message: QUESTION }]));
    expect(composer()).toHaveValue('');
    expect(await screen.findByText(SOURCED_REPLY.paragraphs![0]!.text)).toBeInTheDocument();
    await waitFor(() => expect(reads).toBe(2));
    const list = screen.getByRole('list', { name: 'Conversation' });
    expect(within(list).getAllByRole('listitem')).toHaveLength(2);
    expect(composer()).toHaveFocus();
  });

  it('announces once that the advisor replied', async () => {
    server.use(
      metaWithStrategy(),
      chatThreadOk(() => thread()),
      chatAskOk({ message: ASSISTANT_MESSAGE, remaining_turns: 24 }),
    );
    const user = userEvent.setup();
    renderTab();

    await user.type(await screen.findByRole('textbox', { name: 'Your question' }), QUESTION);
    await user.click(screen.getByRole('button', { name: 'Send' }));

    await waitFor(() => expect(live()).toHaveTextContent('Advisor replied.'));
    expect(mounted.querySelectorAll('[aria-live="polite"]')).toHaveLength(1);
  });

  it('sends with Enter and adds a new line with Shift+Enter', async () => {
    const sent: unknown[] = [];
    server.use(
      metaWithStrategy(),
      chatThreadOk(() => thread()),
      chatAskOk({ message: ASSISTANT_MESSAGE, remaining_turns: 24 }, (body) => sent.push(body)),
    );
    const user = userEvent.setup();
    renderTab();

    await user.type(await screen.findByRole('textbox', { name: 'Your question' }), 'First line');
    await user.keyboard('{Shift>}{Enter}{/Shift}');
    await user.keyboard('second line');
    expect(composer()).toHaveValue('First line\nsecond line');
    expect(sent).toEqual([]);

    await user.keyboard('{Enter}');
    await waitFor(() => expect(sent).toEqual([{ message: 'First line\nsecond line' }]));
  });

  it('ignores Enter while a character is being composed', async () => {
    const sent: unknown[] = [];
    server.use(
      metaWithStrategy(),
      chatThreadOk(() => thread()),
      chatAskOk({ message: ASSISTANT_MESSAGE, remaining_turns: 24 }, (body) => sent.push(body)),
    );
    renderTab();

    const box = await screen.findByRole('textbox', { name: 'Your question' });
    fireEvent.change(box, { target: { value: 'にほん' } });
    fireEvent.compositionStart(box);
    fireEvent.keyDown(box, { key: 'Enter' });
    fireEvent.compositionEnd(box);
    fireEvent.keyDown(box, { key: 'Enter', keyCode: 229 });
    fireEvent.keyDown(box, { key: 'Enter', isComposing: true });
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(sent).toEqual([]);

    fireEvent.keyDown(box, { key: 'Enter' });
    await waitFor(() => expect(sent).toEqual([{ message: 'にほん' }]));
  });

  it('sends nothing for an empty or too long question, and says why', async () => {
    const sent: unknown[] = [];
    server.use(
      metaWithStrategy(),
      chatThreadOk(() => thread({ limits: { max_message_chars: 10, max_user_turns: 25 } })),
      chatAskOk({ message: ASSISTANT_MESSAGE, remaining_turns: 24 }, (body) => sent.push(body)),
    );
    const user = userEvent.setup();
    renderTab();

    await user.click(await screen.findByRole('button', { name: 'Send' }));
    expect(screen.getByText('Write a question first.')).toBeInTheDocument();

    await user.type(composer(), 'Far too long a question');
    expect(screen.getByText('23 / 10')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Send' }));
    expect(screen.getByText('Write a question of up to 10 characters.')).toBeInTheDocument();
    expect(composer()).toHaveAttribute('aria-invalid', 'true');
    expect(sent).toEqual([]);
  });

  it('shows a Thinking row while it waits, announces it, and cancels on request with the question kept', async () => {
    let answered = false;
    server.use(
      metaWithStrategy(),
      chatThreadOk(() => thread()),
      http.post(`${runUrl()}/chat`, async () => {
        await delay('infinite');
        answered = true;
        return HttpResponse.json({ message: ASSISTANT_MESSAGE, remaining_turns: 24 });
      }),
    );
    const user = userEvent.setup();
    renderTab();

    await user.type(await screen.findByRole('textbox', { name: 'Your question' }), QUESTION);
    await user.click(screen.getByRole('button', { name: 'Send' }));

    expect(await screen.findByText('Thinking')).toBeInTheDocument();
    expect(live()).toHaveTextContent('Advisor is answering');
    expect(screen.getByRole('button', { name: 'Send' })).toBeDisabled();
    expect(within(screen.getByRole('list', { name: 'Conversation' })).getByText(QUESTION)).toBeInTheDocument();
    expect(composer()).toHaveValue('');

    await user.click(screen.getByRole('button', { name: 'Cancel' }));

    expect(await screen.findByText('Cancelled. Your question is still here.')).toBeInTheDocument();
    expect(screen.queryByText('Thinking')).not.toBeInTheDocument();
    expect(composer()).toHaveValue(QUESTION);
    expect(live()).toHaveTextContent('');
    expect(screen.queryByRole('list', { name: 'Conversation' })).not.toBeInTheDocument();
    expect(answered).toBe(false);
  });
});

describe('Advisor: errors keep the draft', () => {
  function failing(status: number, code: string, message: string) {
    return http.post(`${runUrl()}/chat`, () => HttpResponse.json({ error: { code, message } }, { status }));
  }

  async function askAndFail() {
    const user = userEvent.setup();
    renderTab();
    await user.type(await screen.findByRole('textbox', { name: 'Your question' }), QUESTION);
    await user.click(screen.getByRole('button', { name: 'Send' }));
  }

  it('says the AI service is busy when the provider fails', async () => {
    server.use(
      metaWithStrategy(),
      chatThreadOk(() => thread()),
      failing(502, 'llm_api_error', 'The AI service is not responding. Please try again.'),
    );
    await askAndFail();

    expect(await screen.findByText('The AI service is busy. Try again in a minute.')).toBeInTheDocument();
    expect(composer()).toHaveValue(QUESTION);
    expect(screen.queryByRole('list', { name: 'Conversation' })).not.toBeInTheDocument();
  });

  it('adds the rephrasing hint when the reply could not be read', async () => {
    server.use(
      metaWithStrategy(),
      chatThreadOk(() => thread()),
      failing(502, 'llm_invalid_response', 'Could not understand the AI reply. Please try again. Try rephrasing the question.'),
    );
    await askAndFail();

    expect(
      await screen.findByText('The AI service is busy. Try again in a minute. Try rephrasing the question.'),
    ).toBeInTheDocument();
    expect(composer()).toHaveValue(QUESTION);
  });

  it('says the connection was lost and keeps the question', async () => {
    server.use(metaWithStrategy(), chatThreadOk(() => thread()), http.post(`${runUrl()}/chat`, () => HttpResponse.error()));
    await askAndFail();

    expect(await screen.findByText('Lost connection. Your question is still here.')).toBeInTheDocument();
    expect(composer()).toHaveValue(QUESTION);
  });

  it('passes on the plain words for a busy thread and for the cooldown', async () => {
    server.use(
      metaWithStrategy(),
      chatThreadOk(() => thread()),
      failing(409, 'chat_busy', 'Wait for the current answer first.'),
    );
    await askAndFail();
    expect(await screen.findByText('Wait for the current answer first.')).toBeInTheDocument();
    expect(composer()).toHaveValue(QUESTION);

    server.use(failing(429, 'chat_cooldown', 'Wait a moment before the next question.'));
    await userEvent.setup().click(screen.getByRole('button', { name: 'Send' }));
    expect(await screen.findByText('Wait a moment before the next question.')).toBeInTheDocument();
    expect(composer()).toHaveValue(QUESTION);
  });
});

describe('Advisor: limits and clearing', () => {
  it('shows how many questions are left only when five or fewer remain', async () => {
    server.use(metaWithStrategy(), chatThreadOk(() => thread({ messages: [USER_MESSAGE, ASSISTANT_MESSAGE], remaining_turns: 6 })));
    const first = renderTab();
    await screen.findByRole('list', { name: 'Conversation' });
    expect(screen.queryByText(/questions? left/)).not.toBeInTheDocument();
    first.view.unmount();

    server.use(chatThreadOk(() => thread({ messages: [USER_MESSAGE, ASSISTANT_MESSAGE], remaining_turns: 3 })));
    const second = renderTab();
    expect(await screen.findByText('3 questions left')).toBeInTheDocument();
    second.view.unmount();

    server.use(chatThreadOk(() => thread({ messages: [USER_MESSAGE, ASSISTANT_MESSAGE], remaining_turns: 1 })));
    renderTab();
    expect(await screen.findByText('1 question left')).toBeInTheDocument();
  });

  it('replaces the composer with a full note and a Clear button when no questions remain', async () => {
    server.use(metaWithStrategy(), chatThreadOk(() => thread({ messages: [USER_MESSAGE, ASSISTANT_MESSAGE], remaining_turns: 0 })));
    renderTab();

    expect(await screen.findByText('This conversation is full.')).toBeInTheDocument();
    expect(screen.queryByRole('textbox', { name: 'Your question' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Send' })).not.toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: 'Clear conversation' })).toHaveLength(1);
    expect(screen.queryByRole('list', { name: 'Follow-up questions' })).not.toBeInTheDocument();
  });

  it('reads the thread again when the backend says the conversation is full', async () => {
    let current = thread({ messages: [USER_MESSAGE, ASSISTANT_MESSAGE], remaining_turns: 1 });
    server.use(
      metaWithStrategy(),
      chatThreadOk(() => current),
      http.post(`${runUrl()}/chat`, () => {
        current = { ...current, remaining_turns: 0 };
        return HttpResponse.json(
          { error: { code: 'chat_limit_reached', message: 'This conversation is full. Clear it to start again.' } },
          { status: 409 },
        );
      }),
    );
    const user = userEvent.setup();
    renderTab();

    await user.type(await screen.findByRole('textbox', { name: 'Your question' }), QUESTION);
    await user.click(screen.getByRole('button', { name: 'Send' }));

    expect(await screen.findByText('This conversation is full. Clear it to start again.')).toBeInTheDocument();
    expect(await screen.findByText('This conversation is full.')).toBeInTheDocument();
    expect(screen.queryByRole('textbox', { name: 'Your question' })).not.toBeInTheDocument();
  });

  it('asks before clearing, with Keep it focused, and clears only on confirmation', async () => {
    let cleared = 0;
    let current = thread({ messages: [USER_MESSAGE, ASSISTANT_MESSAGE], remaining_turns: 24 });
    server.use(
      metaWithStrategy(),
      chatThreadOk(() => current),
      chatClearOk(() => {
        cleared += 1;
        current = thread();
      }),
    );
    const user = userEvent.setup();
    renderTab();

    await user.click(await screen.findByRole('button', { name: 'Clear conversation' }));
    expect(screen.getByRole('heading', { name: 'Clear this conversation?' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Keep it' })).toHaveFocus();
    await user.click(screen.getByRole('button', { name: 'Keep it' }));
    expect(screen.queryByRole('heading', { name: 'Clear this conversation?' })).not.toBeInTheDocument();
    expect(cleared).toBe(0);

    await user.click(screen.getByRole('button', { name: 'Clear conversation' }));
    await user.click(screen.getByRole('button', { name: 'Clear it' }));

    await waitFor(() => expect(cleared).toBe(1));
    expect(await screen.findByText('Ask about your market, competitors, risks, MVP or launch plan.')).toBeInTheDocument();
    expect(screen.queryByRole('list', { name: 'Conversation' })).not.toBeInTheDocument();
  });

  it('says so when the conversation could not be cleared', async () => {
    server.use(
      metaWithStrategy(),
      chatThreadOk(() => thread({ messages: [USER_MESSAGE, ASSISTANT_MESSAGE], remaining_turns: 24 })),
      http.delete(`${runUrl()}/chat`, () =>
        HttpResponse.json({ error: { code: 'chat_busy', message: 'Wait for the current answer first.' } }, { status: 409 }),
      ),
    );
    const user = userEvent.setup();
    renderTab();

    await user.click(await screen.findByRole('button', { name: 'Clear conversation' }));
    await user.click(screen.getByRole('button', { name: 'Clear it' }));

    expect(await screen.findByText('The conversation was not cleared')).toBeInTheDocument();
    expect(screen.getByText('Wait for the current answer first.')).toBeInTheDocument();
    expect(within(screen.getByRole('list', { name: 'Conversation' })).getAllByRole('listitem')).toHaveLength(2);
  });
});

describe('Advisor: unavailable and missing strategy', () => {
  it('explains that questions wait for a finished validation, and asks nothing', async () => {
    let reads = 0;
    server.use(
      metaWithStrategy(),
      chatThreadOk(() => {
        reads += 1;
        return thread();
      }),
    );
    const shown: string[] = [];
    renderTab({ ...STRATEGY_DONE, state: 'cancelled' }, { onShowOverview: () => shown.push('overview') });

    expect(
      await screen.findByText('Questions open once the validation has finished. This one was cancelled.'),
    ).toBeInTheDocument();
    expect(screen.queryByRole('textbox', { name: 'Your question' })).not.toBeInTheDocument();
    await userEvent.setup().click(screen.getByRole('link', { name: 'Open the overview' }));
    expect(shown).toEqual(['overview']);
    expect(reads).toBe(0);
  });

  it('links to the run when there is no result to ask about', async () => {
    server.use(metaWithStrategy());
    renderTab({ ...STRATEGY_DONE, state: 'failed', result: null });

    expect(await screen.findByText('Questions open once the validation has finished. This one did not finish.')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Open the overview' })).toHaveAttribute('href', '/runs/run-123');
  });

  it("shows the backend's reason when it refuses to open the conversation", async () => {
    server.use(
      metaWithStrategy(),
      http.get(`${runUrl()}/chat`, () =>
        HttpResponse.json(
          { error: { code: 'chat_unavailable', message: 'Questions open once the validation has finished.' } },
          { status: 409 },
        ),
      ),
    );
    renderTab();

    expect(await screen.findByText('Questions open once the validation has finished.')).toBeInTheDocument();
    expect(screen.queryByRole('textbox', { name: 'Your question' })).not.toBeInTheDocument();
  });

  it('offers to generate the strategy when the run has none, and sends one request', async () => {
    const bodies: unknown[] = [];
    server.use(
      metaWithStrategy(),
      chatThreadOk(() => thread({ available_sections: ['market', 'competitors'] })),
      strategyOk((body) => bodies.push(body)),
    );
    const user = userEvent.setup();
    renderTab();

    expect(await screen.findByText('Strategy has not been generated yet.')).toBeInTheDocument();
    expect(screen.getByText('This uses 3 AI requests.')).toBeInTheDocument();
    const uses = screen.getByRole('list', { name: 'The Advisor can use:' });
    expect(within(uses).getAllByRole('listitem').map((item) => item.textContent)).toEqual(['Market', 'Competitors']);

    await user.click(screen.getByRole('button', { name: 'Generate strategy' }));
    await waitFor(() => expect(bodies).toEqual([{ mode: 'missing' }]));
  });

  it('makes no strategy offer when the strategy is there', async () => {
    server.use(metaWithStrategy(), chatThreadOk(() => thread()));
    renderTab();

    await screen.findByRole('list', { name: 'Suggested questions' });
    expect(screen.queryByText('Strategy has not been generated yet.')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Generate strategy' })).not.toBeInTheDocument();
  });
});

describe('Advisor: a question written in from elsewhere', () => {
  it('puts the question in the composer and focuses it without sending it', async () => {
    const sent: unknown[] = [];
    const focused: number[] = [];
    server.use(
      metaWithStrategy(),
      chatThreadOk(() => thread()),
      chatAskOk({ message: ASSISTANT_MESSAGE, remaining_turns: 24 }, (body) => sent.push(body)),
    );
    renderTab(STRATEGY_DONE, {
      draft: 'Why are these features in the first release?',
      onDraftChange: () => undefined,
      focusComposer: true,
      onComposerFocused: () => focused.push(1),
    });

    const box = await screen.findByRole('textbox', { name: 'Your question' });
    await waitFor(() => expect(box).toHaveFocus());
    expect(box).toHaveValue('Why are these features in the first release?');
    expect(focused).toEqual([1]);
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(sent).toEqual([]);
  });
});
