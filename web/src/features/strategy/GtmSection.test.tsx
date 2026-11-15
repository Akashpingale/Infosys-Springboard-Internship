import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { Route, Routes } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';

import { RunPage } from '@/features/run/RunPage';
import type { RunDetail } from '@/features/run/useRun';
import { GtmSection } from '@/features/strategy/GtmSection';
import { StrategyTab } from '@/features/strategy/StrategyTab';
import { buildSourceIndex, sourceKey, type PipelineResult } from '@/lib/results';
import { renderWithApp } from '@/test/render';
import { server } from '@/test/server';
import {
  STRATEGY_DONE,
  SYNTHETIC_STRATEGY_RESULT,
  metaWithStrategy,
  runUrl,
  sevenStages,
} from '@/test/strategyHandlers';

type Gtm = NonNullable<PipelineResult['gtm']>;

const RESULT = SYNTHETIC_STRATEGY_RESULT;
const GTM = RESULT.gtm!;
const MVP = RESULT.mvp!;
const SWOT = RESULT.swot!;
const SOURCES = buildSourceIndex(RESULT);

const CHANNELS = [
  'Short demo videos on a messaging app',
  'Cooperative staff referrals',
  'Village demo booths',
  'Cooperative field days',
  'Agri-input retailer counters',
  'Radio farm shows',
];

function show(gtm: Gtm = GTM, mvp: PipelineResult['mvp'] = MVP, swot: PipelineResult['swot'] = SWOT) {
  const opened = vi.fn();
  render(<GtmSection gtm={gtm} mvp={mvp ?? null} swot={swot ?? null} sources={SOURCES} onOpenSource={opened} />);
  return opened;
}

function region(name: string): HTMLElement {
  return screen.getByRole('region', { name });
}

function channelNames(): string[] {
  return within(screen.getByRole('list', { name: 'Channels' }))
    .getAllByRole('article')
    .map((card) => within(card).getByRole('heading').textContent ?? '');
}

function channel(name: string): HTMLElement {
  return screen.getByRole('article', { name });
}

function value(scope: HTMLElement, label: string): HTMLElement {
  const term = within(scope).getByText(label, { selector: 'dt' });
  return term.nextElementSibling as HTMLElement;
}

describe('Go-to-market: positioning', () => {
  it('shows the statement exactly as the backend returned it, with the segment and the six parts', () => {
    show();

    const positioning = region('Positioning');
    expect(within(positioning).getByText(/^For smallholder farmers on rain-fed plots/)).toHaveTextContent(GTM.positioning.statement);
    expect(positioning).toHaveTextContent('Target segment: Smallholder farmers');
    expect(within(positioning).getAllByRole('term').map((term) => term.textContent)).toEqual([
      'For whom',
      'Problem',
      'Category',
      'Key benefit',
      'Alternative',
      'Differentiator',
    ]);
    expect(value(positioning, 'Key benefit')).toHaveTextContent('names the disease and a treatment from one photo');
    expect(within(positioning).getByText('AI interpretation')).toBeInTheDocument();
  });

  it('never rebuilds the statement from its parts', () => {
    show({ ...GTM, positioning: { ...GTM.positioning, statement: 'A statement the backend assembled.' } });

    const positioning = region('Positioning');
    expect(within(positioning).getByText('A statement the backend assembled.')).toBeInTheDocument();
    expect(positioning).not.toHaveTextContent('For smallholder farmers on rain-fed plots who');
  });

  it('marks a differentiator that rests on a gap as a hypothesis, with an icon and a word', () => {
    show();

    const differentiator = value(region('Positioning'), 'Differentiator');
    expect(differentiator).toHaveTextContent("it pairs each diagnosis with treatment advice in the farmer's language");
    const chip = within(differentiator).getByText('Hypothesis');
    expect(chip.querySelector('svg')).toHaveAttribute('aria-hidden', 'true');
    expect(within(differentiator).queryByText('Supported')).not.toBeInTheDocument();
  });

  it('marks a differentiator backed by a competitor fact as supported', () => {
    show({ ...GTM, positioning: { ...GTM.positioning, differentiator_status: 'supported' } });

    const differentiator = value(region('Positioning'), 'Differentiator');
    expect(within(differentiator).getByText('Supported').querySelector('svg')).not.toBeNull();
    expect(within(differentiator).queryByText('Hypothesis')).not.toBeInTheDocument();
  });

  it('opens a source the positioning cites', async () => {
    const user = userEvent.setup();
    const opened = show();

    await user.click(within(region('Positioning')).getByRole('button', { name: /^Source 10: Kisan call centre helpline/ }));

    expect(opened).toHaveBeenCalledWith(sourceKey('competitors', 'S6'));
  });
});

describe('Go-to-market: channels', () => {
  it('keeps the backend order and puts a single "Start here" chip on the first channel', () => {
    show();

    expect(channelNames()).toEqual(CHANNELS);
    expect(screen.getAllByText('Start here')).toHaveLength(1);
    const start = within(channel(CHANNELS[0]!)).getByText('Start here');
    expect(start.querySelector('svg')).toHaveAttribute('aria-hidden', 'true');
  });

  it('never re-ranks, and still shows only one "Start here"', () => {
    const channels = GTM.channels ?? [];
    const flagged = channels.map((entry) => ({ ...entry, start_here: true }));
    show({ ...GTM, channels: [flagged[5]!, flagged[0]!, flagged[2]!] });

    expect(channelNames()).toEqual(['Radio farm shows', CHANNELS[0], CHANNELS[2]]);
    expect(screen.getAllByText('Start here')).toHaveLength(1);
    expect(within(channel('Radio farm shows')).getByText('Start here')).toBeInTheDocument();
  });

  it('gives every audience-fit meter its value in words and numbers', () => {
    show();

    const fits = (GTM.channels ?? []).map((entry) => entry.audience_fit);
    CHANNELS.forEach((name, index) => {
      const fit = value(channel(name), 'Audience fit');
      const meter = fit.querySelector('[aria-hidden="true"]')!;
      expect(meter.children).toHaveLength(5);
      expect(Array.from(meter.children).filter((step) => step.className.includes('bg-primary'))).toHaveLength(
        fits[index]!,
      );
      expect(fit.textContent).toBe(
        { 5: 'Very strong, 5 of 5', 4: 'Strong, 4 of 5', 3: 'Moderate, 3 of 5' }[fits[index] as 3 | 4 | 5],
      );
    });
  });

  it('shows type, role, cost, speed, the first experiment and the success signal in words', () => {
    show();

    const first = channel(CHANNELS[0]!);
    expect(value(first, 'Type')).toHaveTextContent('Digital');
    expect(value(first, 'Role')).toHaveTextContent('Acquisition');
    expect(value(first, 'Cost')).toHaveTextContent('Low');
    expect(value(first, 'First results in')).toHaveTextContent('Days');
    expect(value(first, 'First experiment')).toHaveTextContent(
      'Try short demo videos on a messaging app with a few farmers for two weeks.',
    );
    expect(value(first, 'Success signal')).toHaveTextContent(
      'Farmers who met short demo videos on a messaging app send a second photo.',
    );
    expect(value(channel('Cooperative staff referrals'), 'Type')).toHaveTextContent('Direct sales');
    expect(value(channel('Cooperative staff referrals'), 'Role')).toHaveTextContent('Acquisition and distribution');
    expect(value(channel('Radio farm shows'), 'First results in')).toHaveTextContent('Months');
  });

  it('names the MVP features and the risks a channel is linked to', () => {
    show();

    const field = channel('Cooperative field days');
    expect(
      within(within(field).getByRole('list', { name: 'Uses these features' }))
        .getAllByRole('listitem')
        .map((item) => item.textContent),
    ).toEqual(['Photo-based diagnosis', 'Local language support']);
    expect(
      within(within(field).getByRole('list', { name: 'Addresses these risks' }))
        .getAllByRole('listitem')
        .map((item) => item.textContent),
    ).toEqual(['Cooperatives delay adoption']);
    expect(within(channel('Radio farm shows')).queryByText('Uses these features')).not.toBeInTheDocument();
  });

  it('shows no link to a feature or risk the results do not hold', () => {
    const channels = GTM.channels ?? [];
    show({
      ...GTM,
      channels: [{ ...channels[0]!, uses_feature_ids: ['F99', 'f1'], addresses_risk_ids: ['R99'] }, ...channels.slice(1)],
    });

    const first = channel(CHANNELS[0]!);
    expect(
      within(within(first).getByRole('list', { name: 'Uses these features' }))
        .getAllByRole('listitem')
        .map((item) => item.textContent),
    ).toEqual(['Photo-based diagnosis']);
    expect(within(first).queryByText('Addresses these risks')).not.toBeInTheDocument();
  });

  it('links nothing when the plan has no MVP or SWOT to point to', () => {
    show(GTM, null, null);

    expect(screen.queryByText('Uses these features')).not.toBeInTheDocument();
    expect(screen.queryByText('Addresses these risks')).not.toBeInTheDocument();
  });

  it('notes a channel that may be above a bootstrapped budget, and only that one', () => {
    show();

    const notes = screen.getAllByText('May be above a bootstrapped budget');
    expect(notes).toHaveLength(1);
    expect(within(channel('Radio farm shows')).getByText('May be above a bootstrapped budget')).toBe(notes[0]);
    expect(notes[0]!.querySelector('svg')).toHaveAttribute('aria-hidden', 'true');
  });

  it('opens the source a channel cites', async () => {
    const user = userEvent.setup();
    const opened = show();

    await user.click(within(channel(CHANNELS[0]!)).getByRole('button', { name: /^Source 2: Plantix crop doctor app/ }));

    expect(opened).toHaveBeenCalledWith(sourceKey('market', 'S2'));
  });
});

describe('Go-to-market: early customers, launch plan and messages', () => {
  it('shows each early-customer tactic as a card with where, offer and measure', () => {
    show();

    const cards = within(screen.getByRole('list', { name: 'Early customers' })).getAllByRole('article');
    expect(cards.map((card) => within(card).getByRole('heading').textContent)).toEqual([
      'Free diagnosis week at a cooperative',
      'Pilot with lead farmers',
      'Retailer counter sign-ups',
      'Local language demo calls',
    ]);
    expect(value(cards[0]!, 'Where to find them')).toHaveTextContent('farming cooperatives with member meetings');
    expect(value(cards[0]!, 'Offer')).toHaveTextContent('free photo diagnosis for every member for a week');
    expect(value(cards[0]!, 'How to measure')).toHaveTextContent('count members who send a second photo');
    expect(within(cards[1]!).getByText('Assumption')).toBeInTheDocument();
  });

  it('lists the launch phases in order as a numbered list, with goal and actions', () => {
    show();

    const plan = screen.getByRole('list', { name: 'Launch plan' });
    expect(plan.tagName).toBe('OL');
    const phases = Array.from(plan.children);
    expect(phases.map((phase) => within(phase as HTMLElement).getByRole('heading').textContent)).toEqual([
      'Before launch',
      'Launch',
      'First 90 days',
    ]);
    expect(phases[1]).toHaveTextContent('Goal: Win the first cooperative');
    expect(within(phases[1] as HTMLElement).getAllByRole('listitem').map((item) => item.textContent)).toEqual([
      'Run a free diagnosis week',
      'Share demo videos in farmer groups',
      'Train cooperative staff',
    ]);
  });

  it('shows only the phases returned, never inventing one', () => {
    show({ ...GTM, launch_phases: (GTM.launch_phases ?? []).slice(0, 2) });

    const plan = screen.getByRole('list', { name: 'Launch plan' });
    expect(plan.children).toHaveLength(2);
    expect(plan).not.toHaveTextContent('First 90 days');
  });

  it('shows the key messages as a small table, saying when no proof was named', () => {
    const messages = GTM.key_messages ?? [];
    show({ ...GTM, key_messages: [messages[0]!, { ...messages[1]!, proof_needed: '' }] });

    const table = screen.getByRole('table', { name: 'Key messages, by audience.' });
    expect(within(table).getAllByRole('columnheader').map((cell) => cell.textContent)).toEqual([
      'Audience',
      'Message',
      'Proof needed',
    ]);
    const rows = within(table).getAllByRole('row').slice(1);
    expect(rows.map((row) => within(row).getByRole('rowheader').textContent)).toEqual([
      'Smallholder farmers',
      'Cooperative staff',
    ]);
    expect(rows[0]).toHaveTextContent('Send one photo and get the disease name and a treatment');
    expect(rows[0]).toHaveTextContent('Pilot farmers who acted on the advice');
    expect(rows[1]).toHaveTextContent('Not given');
  });

  it('shows no percentage anywhere', () => {
    show();

    expect(document.body.textContent).not.toMatch(/\d+(\.\d+)?\s?%/);
  });
});

describe('Go-to-market: missing inputs', () => {
  it('says plainly when the plan was made without the risks or the MVP', () => {
    show({ ...GTM, quality: { ...GTM.quality!, inputs_missing: ['swot', 'mvp'] } }, null, null);

    expect(screen.getByText('Risks were not considered when planning go-to-market.')).toBeInTheDocument();
    expect(
      screen.getByText('The plan is not tied to a feature set because no MVP recommendation was available.'),
    ).toBeInTheDocument();
  });

  it('has no such notes when both were used', () => {
    show();

    expect(screen.queryByText('Risks were not considered when planning go-to-market.')).not.toBeInTheDocument();
    expect(screen.queryByText(/not tied to a feature set/)).not.toBeInTheDocument();
  });
});

describe('Go-to-market: layout', () => {
  it('stacks channel and tactic cards in one column below the widest breakpoint, with one layout in the page', () => {
    show();

    for (const name of ['Channels', 'Early customers']) {
      const classes = screen.getByRole('list', { name }).className.split(/\s+/);
      expect(classes).toContain('grid');
      expect(classes).toContain('xl:grid-cols-2');
      expect(classes.filter((entry) => /^grid-cols-/.test(entry))).toEqual([]);
    }
    expect(screen.getAllByRole('article')).toHaveLength(10);
    expect(screen.getAllByText('Radio farm shows')).toHaveLength(1);
    for (const article of screen.getAllByRole('article')) {
      expect(article.className).toContain('min-w-0');
    }
  });
});

describe('Go-to-market in the Strategy tab', () => {
  function withResult(result: PipelineResult, extra: Partial<RunDetail> = {}): RunDetail {
    return { ...STRATEGY_DONE, result, ...extra };
  }

  function showTab(run: RunDetail) {
    renderWithApp(
      <StrategyTab run={run} result={run.result!} sources={buildSourceIndex(run.result!)} onOpenSource={vi.fn()} />,
    );
  }

  it('renders the go-to-market plan as its own section', () => {
    server.use(metaWithStrategy());
    showTab(STRATEGY_DONE);

    const section = region('Go-to-market');
    expect(within(section).getByRole('region', { name: 'Positioning' })).toBeInTheDocument();
    expect(within(section).getByRole('region', { name: 'Channels' })).toBeInTheDocument();
  });

  it('has the launch plan as the only numbered list in the tab', () => {
    server.use(metaWithStrategy());
    showTab(STRATEGY_DONE);

    const numbered = document.querySelectorAll('ol');
    expect(numbered).toHaveLength(1);
    expect(numbered[0]).toBe(screen.getByRole('list', { name: 'Launch plan' }));
  });

  it('says the go-to-market part could not be completed and offers a retry', () => {
    server.use(metaWithStrategy());
    showTab(
      withResult(
        {
          ...RESULT,
          status: 'partial',
          gtm: null,
          errors: [{ stage: 'go_to_market', code: 'llm_api_error', message: 'The AI service is busy right now.' }],
        },
        { stages: sevenStages(['done', 'done', 'failed']) },
      ),
    );

    const section = region('Go-to-market');
    expect(within(section).getByText('This part could not be completed.')).toBeInTheDocument();
    expect(section).toHaveTextContent('The AI service is busy right now.');
    expect(within(section).getByRole('button', { name: 'Try again' })).toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: 'Try again' })).toHaveLength(1);
  });

  it('shows the reason the go-to-market part was skipped', () => {
    server.use(metaWithStrategy());
    showTab(
      withResult(
        {
          ...RESULT,
          status: 'partial',
          gtm: null,
          notices: [
            {
              stage: 'go_to_market',
              code: 'strategy_stage_skipped',
              severity: 'warning',
              message: 'This part was skipped because no analysis was available to build on.',
              detail: 'Planning go-to-market: skipped',
            },
          ],
        },
        { stages: sevenStages(['done', 'done', 'skipped']) },
      ),
    );

    const section = region('Go-to-market');
    expect(within(section).getByText('Skipped')).toBeInTheDocument();
    expect(section).toHaveTextContent('This part was skipped because no analysis was available to build on.');
  });

  it('shows a placeholder while the go-to-market part is being prepared', () => {
    server.use(metaWithStrategy());
    showTab(
      withResult(
        { ...RESULT, gtm: null },
        { state: 'running', stages: sevenStages(['done', 'done', 'running']) },
      ),
    );

    const section = region('Go-to-market');
    expect(within(section).getByText('This part is being prepared.').parentElement).toHaveAttribute('aria-busy', 'true');
  });

  it('lists a channel in the drawer of the source it cites', async () => {
    server.use(metaWithStrategy(), http.get(runUrl(), () => HttpResponse.json(STRATEGY_DONE)));
    const user = userEvent.setup();
    renderWithApp(
      <Routes>
        <Route path="/runs/:runId" element={<RunPage />} />
      </Routes>,
      { route: '/runs/run-123' },
    );

    await user.click(await screen.findByRole('tab', { name: 'Strategy' }));
    await user.click(within(channel(CHANNELS[0]!)).getByRole('button', { name: /^Source 2: Plantix crop doctor app/ }));

    const drawer = await screen.findByRole('dialog', { name: 'Plantix crop doctor app' });
    const cited = within(drawer).getByText('Go-to-market: Channels').parentElement!;
    expect(cited).toHaveTextContent(CHANNELS[0]!);
  });
});
