import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { Route, Routes } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';

import { RunPage } from '@/features/run/RunPage';
import type { RunDetail } from '@/features/run/useRun';
import { MvpSection } from '@/features/strategy/MvpSection';
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

type Mvp = NonNullable<PipelineResult['mvp']>;

const RESULT = SYNTHETIC_STRATEGY_RESULT;
const MVP = RESULT.mvp!;
const SWOT = RESULT.swot!;
const SOURCES = buildSourceIndex(RESULT);

const FIRST = [
  'Photo-based diagnosis',
  'Treatment advice',
  'Local language support',
  'Photo quality guide',
  'Offline photo capture',
  'Advice update log',
];
const LATER = ['Cooperative dashboard', 'Expert chat'];

function show(mvp: Mvp = MVP, swot: PipelineResult['swot'] = SWOT) {
  const opened = vi.fn();
  render(<MvpSection mvp={mvp} swot={swot ?? null} sources={SOURCES} onOpenSource={opened} />);
  return opened;
}

function list(name: string): HTMLElement {
  return screen.getByRole('list', { name });
}

function names(name: string): string[] {
  return within(list(name))
    .getAllByRole('article')
    .map((card) => within(card).getByRole('heading').textContent ?? '');
}

function card(name: string): HTMLElement {
  return screen.getByRole('article', { name });
}

describe('MVP plan: capacity', () => {
  it('shows the planned effort against the capacity, in words, with the assumptions behind it', () => {
    show();

    expect(screen.getByText('Planned 4.5 of 4.8 person-months')).toBeInTheDocument();
    expect(screen.getByText('Based on a team of 2 and 4 months to the first release.')).toBeInTheDocument();
    expect(screen.queryByText('Over capacity')).not.toBeInTheDocument();
    expect(screen.queryByRole('list', { name: 'Assumed resources' })).not.toBeInTheDocument();
  });

  it('warns with an icon and a word when the essential features do not fit', () => {
    show({ ...MVP, planned_person_months: 6, capacity_person_months: 2.4, over_capacity: true });

    expect(screen.getByText('Planned 6 of 2.4 person-months')).toBeInTheDocument();
    const chip = screen.getByText('Over capacity');
    expect(chip.querySelector('svg')).toHaveAttribute('aria-hidden', 'true');
    expect(
      screen.getByText(
        'The essential features need more effort than your team and time allow. Narrow the idea or allow more time.',
      ),
    ).toBeInTheDocument();
  });

  it('shows a chip for each resource the plan assumed, with the value used', () => {
    show({
      ...MVP,
      constraints_used: { ...MVP.constraints_used, team_size: 2, months_to_mvp: 3 },
      quality: { ...MVP.quality!, constraints_assumed: ['team_size', 'months_to_mvp'] },
    });

    const chips = within(list('Assumed resources')).getAllByRole('listitem');
    expect(chips.map((chip) => chip.textContent)).toEqual(['Assumed: team of 2', 'Assumed: 3 months']);
    expect(screen.getByText('Based on a team of 2 and 3 months to the first release.')).toBeInTheDocument();
  });
});

describe('MVP plan: the two lists', () => {
  it('splits the features into the first release and later, in the order the backend ranked them', () => {
    show();

    expect(names('In the first release')).toEqual(FIRST);
    expect(names('Later')).toEqual(LATER);
    expect(
      within(list('In the first release'))
        .getAllByRole('article')
        .map((entry) => within(entry).getByText(/^Rank \d+$/).textContent),
    ).toEqual(['Rank 1', 'Rank 2', 'Rank 3', 'Rank 4', 'Rank 5', 'Rank 6']);
  });

  it('never re-ranks: a list out of score order stays as given', () => {
    const features = MVP.features ?? [];
    const reordered = [features[5]!, features[0]!, features[3]!, features[7]!, features[6]!];
    show({ ...MVP, features: reordered });

    expect(names('In the first release')).toEqual(['Advice update log', 'Photo-based diagnosis', 'Photo quality guide']);
    expect(names('Later')).toEqual(['Expert chat', 'Cooperative dashboard']);
    expect(within(card('Advice update log')).getByText('Rank 6')).toBeInTheDocument();
  });

  it('says so when a list is empty', () => {
    show({ ...MVP, features: (MVP.features ?? []).filter((feature) => feature.tier === 'mvp') });

    const later = screen.getByRole('region', { name: 'Later' });
    expect(later).toHaveTextContent('0 features');
    expect(within(later).getByText('No features in this list.')).toBeInTheDocument();
  });
});

describe('MVP plan: a feature card', () => {
  it('shows rank, tier, effort as an AI estimate, score and the three ratings as labelled values', () => {
    show();

    const first = card('Photo-based diagnosis');
    expect(within(first).getByText('Rank 1')).toBeInTheDocument();
    expect(within(first).getByText('First release').querySelector('svg')).not.toBeNull();
    expect(within(first).getByText('Effort: M, AI estimate')).toBeInTheDocument();
    expect(first).toHaveTextContent('Score3.80 of 5');
    expect(first).toHaveTextContent('Need5 of 5');
    expect(first).toHaveTextContent('Differentiation2 of 5');
    expect(first).toHaveTextContent('Feasibility4 of 5');
    expect(first).toHaveTextContent('Photo-based diagnosis answers a need named in the facts.');
    expect(within(first).getByText('From your idea')).toBeInTheDocument();

    const later = card('Cooperative dashboard');
    expect(within(later).getByText('Later').querySelector('svg')).not.toBeNull();
    expect(within(later).getByText('Effort: L, AI estimate')).toBeInTheDocument();
    expect(later).toHaveTextContent(
      'Why later: It does not fit in the 4.8 person-months the team has, after the features ranked above it.',
    );
    expect(first).not.toHaveTextContent('Why later');
  });

  it('marks the founder\u2019s own features and the suggested ones', () => {
    show();

    expect(within(card('Treatment advice')).getByText('Your feature')).toBeInTheDocument();
    expect(within(card('Photo quality guide')).getByText('Suggested')).toBeInTheDocument();
    expect(within(card('Offline photo capture')).getByText('Suggested')).toBeInTheDocument();
    expect(screen.getAllByText('Your feature')).toHaveLength(3);
    expect(screen.getAllByText('Suggested')).toHaveLength(5);
  });

  it('names the risks a feature reduces, taken from the SWOT result', () => {
    show();

    const treatment = card('Treatment advice');
    expect(within(treatment).getByText('Reduces these risks')).toBeInTheDocument();
    expect(within(treatment).getAllByRole('listitem').map((item) => item.textContent)).toEqual([
      'Wrong diagnosis on poor photos',
    ]);
    expect(within(card('Cooperative dashboard')).getByText('Cooperatives delay adoption')).toBeInTheDocument();
    expect(within(card('Advice update log')).getByText('Advice goes out of date')).toBeInTheDocument();
    expect(within(card('Photo-based diagnosis')).queryByText('Reduces these risks')).not.toBeInTheDocument();
  });

  it('opens the source a feature cites', async () => {
    const user = userEvent.setup();
    const opened = show();

    await user.click(within(card('Local language support')).getByRole('button', { name: /^Source 5: Plantix/ }));

    expect(opened).toHaveBeenCalledWith(sourceKey('competitors', 'S1'));
  });

  it('handles a plan made without the SWOT: no risk links, and a plain note', () => {
    show({ ...MVP, quality: { ...MVP.quality!, inputs_missing: ['swot'] } }, null);

    expect(screen.getByText('Risks were not considered when choosing features.')).toBeInTheDocument();
    expect(screen.queryByText('Reduces these risks')).not.toBeInTheDocument();
    expect(names('In the first release')).toEqual(FIRST);
  });

  it('has no note about risks when the SWOT was used', () => {
    show();

    expect(screen.queryByText('Risks were not considered when choosing features.')).not.toBeInTheDocument();
  });
});

describe('MVP plan: ranking and metrics', () => {
  it('explains how the ranking works with the documented weights and constants', async () => {
    const user = userEvent.setup();
    show();

    const summary = screen.getByText('How the ranking works');
    const details = summary.closest('details')!;
    expect(details.open).toBe(false);
    await user.click(summary);
    expect(details.open).toBe(true);
    expect(details).toHaveTextContent('Score = 0.4 × need + 0.3 × differentiation + 0.3 × feasibility.');
    expect(details).toHaveTextContent('Features essential to the idea come first, then higher scores, then lower effort.');
    expect(details).toHaveTextContent('S is 0.5, M is 1, L is 2.');
    expect(details).toHaveTextContent('Capacity = team size × months × 0.6');
    expect(details).toHaveTextContent('These weights are planning rules of thumb, not facts about your market.');
  });

  it('lists the success metrics, with a target only where one was given, labelled an assumption', () => {
    show();

    const metrics = screen.getByRole('region', { name: 'Success metrics' });
    const items = within(metrics).getAllByRole('listitem');
    expect(items).toHaveLength(3);
    expect(items[0]).toHaveTextContent('Weekly diagnoses per farmer');
    expect(items[0]).toHaveTextContent('Count diagnoses per pilot farmer each week.');
    expect(items[0]).toHaveTextContent('Suggested target, an assumption: Most pilot farmers use it weekly');
    expect(items[1]).not.toHaveTextContent('Suggested target');
    expect(within(items[1]!).getByText('Assumption')).toBeInTheDocument();
  });

  it('shows no percentage anywhere', () => {
    show();

    expect(document.body.textContent).not.toMatch(/\d+(\.\d+)?\s?%/);
  });
});

describe('MVP plan: mobile layout', () => {
  it('stacks the cards in one column below the widest breakpoint, with one layout in the page', () => {
    show();

    for (const name of ['In the first release', 'Later']) {
      const classes = list(name).className.split(/\s+/);
      expect(classes).toContain('grid');
      expect(classes).toContain('xl:grid-cols-2');
      expect(classes.filter((entry) => /^grid-cols-/.test(entry))).toEqual([]);
    }
    expect(screen.getAllByRole('article')).toHaveLength(8);
    expect(screen.getAllByText('Photo-based diagnosis')).toHaveLength(1);
    for (const article of screen.getAllByRole('article')) {
      expect(article.className).toContain('min-w-0');
    }
  });
});

describe('MVP plan in the Strategy tab', () => {
  function withResult(result: PipelineResult, extra: Partial<RunDetail> = {}): RunDetail {
    return { ...STRATEGY_DONE, result, ...extra };
  }

  function showTab(run: RunDetail) {
    renderWithApp(
      <StrategyTab run={run} result={run.result!} sources={buildSourceIndex(run.result!)} onOpenSource={vi.fn()} />,
    );
  }

  it('renders the MVP plan as its own section', () => {
    server.use(metaWithStrategy());
    showTab(STRATEGY_DONE);

    const section = screen.getByRole('region', { name: 'MVP plan' });
    expect(within(section).getByText('Planned 4.5 of 4.8 person-months')).toBeInTheDocument();
  });

  it('says the MVP part could not be completed and offers a retry, while SWOT stays', () => {
    server.use(metaWithStrategy());
    showTab(
      withResult(
        {
          ...RESULT,
          status: 'partial',
          mvp: null,
          errors: [{ stage: 'mvp_recommendation', code: 'llm_api_error', message: 'The AI service is busy right now.' }],
        },
        { stages: sevenStages(['done', 'failed', 'done']) },
      ),
    );

    const section = screen.getByRole('region', { name: 'MVP plan' });
    expect(within(section).getByText('This part could not be completed.')).toBeInTheDocument();
    expect(section).toHaveTextContent('The AI service is busy right now.');
    expect(within(section).getByRole('button', { name: 'Try again' })).toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: 'Try again' })).toHaveLength(1);
    expect(screen.getByRole('region', { name: 'Strengths' })).toBeInTheDocument();
  });

  it('gives each failed section its own retry, sends one request, and blocks both while it is pending', async () => {
    const bodies: unknown[] = [];
    let release: () => void = () => {};
    const held = new Promise<void>((resolve) => {
      release = resolve;
    });
    server.use(
      metaWithStrategy(),
      http.post(`${runUrl()}/strategy`, async ({ request }) => {
        bodies.push(await request.json());
        await held;
        return HttpResponse.json({ run_id: 'run-123', state: 'queued' }, { status: 202 });
      }),
    );
    const user = userEvent.setup();
    showTab(
      withResult(
        {
          ...RESULT,
          status: 'partial',
          swot: null,
          mvp: null,
          errors: [
            { stage: 'swot_risk', code: 'llm_api_error', message: 'The AI service is busy right now.' },
            { stage: 'mvp_recommendation', code: 'llm_api_error', message: 'The AI service is busy right now.' },
          ],
        },
        { stages: sevenStages(['failed', 'failed', 'done']) },
      ),
    );

    const swotRetry = within(screen.getByRole('region', { name: 'SWOT' })).getByRole('button', { name: 'Try again' });
    const mvpRetry = within(screen.getByRole('region', { name: 'MVP plan' })).getByRole('button', { name: 'Try again' });
    expect(screen.getAllByRole('button', { name: 'Try again' })).toHaveLength(2);

    await user.click(mvpRetry);

    await waitFor(() => expect(bodies).toEqual([{ mode: 'missing' }]));
    expect(swotRetry).toBeDisabled();
    expect(mvpRetry).toBeDisabled();
    await user.click(swotRetry);
    expect(bodies).toHaveLength(1);

    release();
    await waitFor(() => expect(mvpRetry).toBeEnabled());
    expect(bodies).toEqual([{ mode: 'missing' }]);
  });

  it('shows the reason the MVP part was skipped', () => {
    server.use(metaWithStrategy());
    showTab(
      withResult(
        {
          ...RESULT,
          status: 'partial',
          mvp: null,
          notices: [
            {
              stage: 'mvp_recommendation',
              code: 'strategy_stage_skipped',
              severity: 'warning',
              message: 'This part was skipped because no analysis was available to build on.',
              detail: 'Recommending MVP features: skipped',
            },
          ],
        },
        { stages: sevenStages(['done', 'skipped', 'done']) },
      ),
    );

    const section = screen.getByRole('region', { name: 'MVP plan' });
    expect(within(section).getByText('Skipped')).toBeInTheDocument();
    expect(section).toHaveTextContent('This part was skipped because no analysis was available to build on.');
  });

  it('lists an MVP feature in the drawer of the source it cites', async () => {
    server.use(metaWithStrategy(), http.get(runUrl(), () => HttpResponse.json(STRATEGY_DONE)));
    const user = userEvent.setup();
    renderWithApp(
      <Routes>
        <Route path="/runs/:runId" element={<RunPage />} />
      </Routes>,
      { route: '/runs/run-123' },
    );

    await user.click(await screen.findByRole('tab', { name: 'Strategy' }));
    const feature = screen.getByRole('article', { name: 'Photo-based diagnosis' });
    await user.click(within(feature).getByRole('button', { name: /^Source 4: Farmer survey/ }));

    const drawer = await screen.findByRole('dialog', { name: 'Farmer survey' });
    const cited = within(drawer).getByText('MVP plan').parentElement!;
    expect(cited).toHaveTextContent('Photo-based diagnosis');
  });
});
