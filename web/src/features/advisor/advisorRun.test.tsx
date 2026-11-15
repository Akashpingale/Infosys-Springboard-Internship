import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';

import { Providers } from '@/app/providers';
import { ADVISOR_QUESTIONS } from '@/features/advisor/AdvisorTab';
import type { ChatMessage, ChatThread } from '@/features/advisor/useChat';
import { RunPage } from '@/features/run/RunPage';
import type { RunDetail } from '@/features/run/useRun';
import { StrategyTab } from '@/features/strategy/StrategyTab';
import { buildSourceIndex } from '@/lib/results';
import { renderWithApp, testQueryClient } from '@/test/render';
import { server } from '@/test/server';
import {
  ASSISTANT_MESSAGE,
  EMPTY_THREAD,
  STRATEGY_DONE,
  SYNTHETIC_STRATEGY_RESULT,
  USER_MESSAGE,
  chatThreadOk,
  metaWithStrategy,
  runUrl,
  sevenStages,
} from '@/test/strategyHandlers';

const ASK = 'Ask the advisor about this';

const CITED: ChatMessage = {
  ...ASSISTANT_MESSAGE,
  id: 'msg-9',
  paragraphs: [
    {
      text: 'Plantix is the closest competitor in the results.',
      basis: 'sourced',
      sections: ['competitors'],
      sources: [{ analysis: 'competitors', id: 'S1' }],
    },
  ],
};

function show(run: RunDetail) {
  return http.get(runUrl(), () => HttpResponse.json(run));
}

function watchAsks() {
  const asked: unknown[] = [];
  return {
    asked,
    handler: http.post(`${runUrl()}/chat`, async ({ request }) => {
      asked.push(await request.json());
      return HttpResponse.json({ message: ASSISTANT_MESSAGE, remaining_turns: 24 });
    }),
  };
}

function open() {
  return renderWithApp(
    <Routes>
      <Route path="/runs/:runId" element={<RunPage />} />
    </Routes>,
    { route: '/runs/run-123' },
  );
}

function composer(): HTMLTextAreaElement {
  return screen.getByRole('textbox', { name: 'Your question' }) as HTMLTextAreaElement;
}

describe('Ask the advisor about this', () => {
  it('ends every Strategy section with the button', async () => {
    server.use(show(STRATEGY_DONE), metaWithStrategy());
    const user = userEvent.setup();
    open();

    await user.click(await screen.findByRole('tab', { name: 'Strategy' }));

    for (const name of ['SWOT', 'Risks', 'MVP plan', 'Go-to-market']) {
      const section = screen.getByRole('region', { name });
      const buttons = within(section).getAllByRole('button', { name: ASK });
      expect(buttons, name).toHaveLength(1);
      expect(buttons[0]).toHaveAccessibleDescription(name);
      expect(section.lastElementChild).toContainElement(buttons[0]!);
    }
  });

  it('opens the Advisor with the question written in and focused, and sends nothing', async () => {
    const { asked, handler } = watchAsks();
    server.use(show(STRATEGY_DONE), metaWithStrategy(), chatThreadOk(() => EMPTY_THREAD), handler);
    const user = userEvent.setup();
    open();

    await user.click(await screen.findByRole('tab', { name: 'Strategy' }));
    await user.click(within(screen.getByRole('region', { name: 'Risks' })).getByRole('button', { name: ASK }));

    expect(screen.getByRole('tab', { name: 'Advisor' })).toHaveAttribute('aria-selected', 'true');
    const box = await screen.findByRole('textbox', { name: 'Your question' });
    expect(box).toHaveValue(ADVISOR_QUESTIONS.risks);
    await waitFor(() => expect(box).toHaveFocus());
    await new Promise((resolve) => setTimeout(resolve, 100));
    expect(asked).toEqual([]);
  });

  it('writes in the question of the section it was pressed in', async () => {
    server.use(show(STRATEGY_DONE), metaWithStrategy(), chatThreadOk(() => EMPTY_THREAD));
    const user = userEvent.setup();
    open();

    const pairs: [string, string][] = [
      ['SWOT', ADVISOR_QUESTIONS.swot],
      ['MVP plan', ADVISOR_QUESTIONS.mvp],
      ['Go-to-market', ADVISOR_QUESTIONS.gtm],
    ];
    for (const [name, question] of pairs) {
      await user.click(await screen.findByRole('tab', { name: 'Strategy' }));
      await user.click(within(await screen.findByRole('region', { name })).getByRole('button', { name: ASK }));
      expect(await screen.findByRole('textbox', { name: 'Your question' })).toHaveValue(question);
    }
  });

  it('is offered at the end of the Market and Competitors tabs too', async () => {
    const { asked, handler } = watchAsks();
    server.use(show(STRATEGY_DONE), metaWithStrategy(), chatThreadOk(() => EMPTY_THREAD), handler);
    const user = userEvent.setup();
    open();

    await user.click(await screen.findByRole('tab', { name: 'Market' }));
    const market = within(screen.getByRole('tabpanel')).getAllByRole('button', { name: ASK });
    expect(market).toHaveLength(1);
    await user.click(market[0]!);
    expect(await screen.findByRole('textbox', { name: 'Your question' })).toHaveValue(ADVISOR_QUESTIONS.market);

    await user.click(screen.getByRole('tab', { name: 'Competitors' }));
    const competitors = within(screen.getByRole('tabpanel')).getAllByRole('button', { name: ASK });
    expect(competitors).toHaveLength(1);
    await user.click(competitors[0]!);
    expect(await screen.findByRole('textbox', { name: 'Your question' })).toHaveValue(ADVISOR_QUESTIONS.competitors);
    expect(asked).toEqual([]);
  });

  it('is not offered on a part that could not be completed', async () => {
    server.use(metaWithStrategy());
    const result = {
      ...SYNTHETIC_STRATEGY_RESULT,
      status: 'partial' as const,
      gtm: null,
      errors: [{ stage: 'go_to_market', code: 'llm_api_error', message: 'The AI service is busy right now.' }],
    };
    const run: RunDetail = { ...STRATEGY_DONE, result, stages: sevenStages(['done', 'done', 'failed']) };
    const onAsk = vi.fn();
    renderWithApp(
      <StrategyTab run={run} result={result} sources={buildSourceIndex(result)} onOpenSource={() => undefined} onAsk={onAsk} />,
    );

    const gtm = screen.getByRole('region', { name: 'Go-to-market' });
    expect(within(gtm).queryByRole('button', { name: ASK })).not.toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: ASK })).toHaveLength(3);

    await userEvent.setup().click(within(screen.getByRole('region', { name: 'MVP plan' })).getByRole('button', { name: ASK }));
    expect(onAsk).toHaveBeenCalledWith(ADVISOR_QUESTIONS.mvp);
  });

  it('is not offered when the page gives the tab nowhere to send it', () => {
    server.use(metaWithStrategy());
    const result = SYNTHETIC_STRATEGY_RESULT;
    renderWithApp(
      <StrategyTab run={STRATEGY_DONE} result={result} sources={buildSourceIndex(result)} onOpenSource={() => undefined} />,
    );

    expect(screen.queryByRole('button', { name: ASK })).not.toBeInTheDocument();
  });
});

describe('Advisor on the run page', () => {
  it('keeps the thread and the draft when the reader moves to another tab and back, and on a re-render', async () => {
    let reads = 0;
    const saved: ChatThread = { ...EMPTY_THREAD, messages: [USER_MESSAGE, ASSISTANT_MESSAGE], remaining_turns: 24 };
    server.use(
      show(STRATEGY_DONE),
      metaWithStrategy(),
      chatThreadOk(() => {
        reads += 1;
        return saved;
      }),
    );
    const user = userEvent.setup();
    const client = testQueryClient();
    const page = () => (
      <Providers client={client}>
        <MemoryRouter initialEntries={['/runs/run-123']}>
          <Routes>
            <Route path="/runs/:runId" element={<RunPage />} />
          </Routes>
        </MemoryRouter>
      </Providers>
    );
    const view = render(page());

    await user.click(await screen.findByRole('tab', { name: 'Advisor' }));
    expect(await screen.findByText(ASSISTANT_MESSAGE.paragraphs![0]!.text)).toBeInTheDocument();
    await user.type(composer(), 'A draft in progress');

    await user.click(screen.getByRole('tab', { name: 'Overview' }));
    expect(screen.queryByRole('list', { name: 'Conversation' })).not.toBeInTheDocument();
    await user.click(screen.getByRole('tab', { name: 'Advisor' }));

    const list = await screen.findByRole('list', { name: 'Conversation' });
    expect(within(list).getAllByRole('listitem')).toHaveLength(2);
    expect(composer()).toHaveValue('A draft in progress');

    view.rerender(page());
    expect(within(await screen.findByRole('list', { name: 'Conversation' })).getAllByRole('listitem')).toHaveLength(2);
    expect(composer()).toHaveValue('A draft in progress');
    expect(reads).toBeGreaterThanOrEqual(2);
  });

  it('opens a cited source in the same drawer as the other tabs', async () => {
    server.use(
      show(STRATEGY_DONE),
      metaWithStrategy(),
      chatThreadOk(() => ({ ...EMPTY_THREAD, messages: [USER_MESSAGE, CITED], remaining_turns: 24 })),
    );
    const user = userEvent.setup();
    open();

    await user.click(await screen.findByRole('tab', { name: 'Advisor' }));
    const reply = await screen.findByText(/Plantix is the closest competitor/);
    await user.click(within(reply).getByRole('button', { name: /Plantix crop doctor app\. Open the source details\./ }));

    const drawer = await screen.findByRole('dialog');
    expect(within(drawer).getByRole('heading', { name: 'Plantix crop doctor app' })).toBeInTheDocument();
  });
});
