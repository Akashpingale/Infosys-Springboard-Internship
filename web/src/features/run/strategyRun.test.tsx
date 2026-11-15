import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { Route, Routes, useLocation, useParams } from 'react-router-dom';
import { describe, expect, it } from 'vitest';

import { TABS } from '@/features/results/ResultsHeader';
import { RunPage } from '@/features/run/RunPage';
import { StageTracker } from '@/features/run/StageTracker';
import { useGenerateStrategy, useRun, type RunDetail } from '@/features/run/useRun';
import { renderWithApp } from '@/test/render';
import { DONE, RUNNING } from '@/test/runFixtures';
import { server } from '@/test/server';
import {
  EMPTY_THREAD,
  STRATEGY_DONE,
  STRATEGY_RUNNING,
  STRATEGY_STAGE_LABELS,
  chatThreadOk,
  metaWithStrategy,
  runUrl,
  strategyOk,
} from '@/test/strategyHandlers';

const SEVEN = ['Overview', 'Market', 'Competitors', 'Strategy', 'Advisor', 'Sources', 'Run details'];

function show(run: RunDetail) {
  return http.get(runUrl(), () => HttpResponse.json(run));
}

function open() {
  return renderWithApp(
    <Routes>
      <Route path="/runs/:runId" element={<RunPage />} />
    </Routes>,
    { route: '/runs/run-123' },
  );
}

describe('Stage tracker: rows come from the run', () => {
  it('shows four rows for a run without strategy', () => {
    render(<StageTracker run={RUNNING} onCancel={() => undefined} />);

    expect(within(screen.getByRole('list')).getAllByRole('listitem')).toHaveLength(4);
    for (const [, label] of STRATEGY_STAGE_LABELS) {
      expect(screen.queryByText(label)).not.toBeInTheDocument();
    }
  });

  it('shows seven rows, with the three strategy labels the backend sent, when strategy was asked for', () => {
    render(<StageTracker run={STRATEGY_RUNNING} onCancel={() => undefined} />);

    const rows = within(screen.getByRole('list')).getAllByRole('listitem');
    expect(rows).toHaveLength(7);
    expect(rows.slice(4).map((row) => row.textContent)).toEqual([
      'Assessing strengths and risksDone9.5 s',
      'Recommending MVP featuresRunning9.5 s',
      'Planning go-to-marketWaiting',
    ]);
  });

  it('announces a running strategy stage like any other', async () => {
    render(<StageTracker run={STRATEGY_RUNNING} onCancel={() => undefined} />);

    const live = document.querySelector('[aria-live="polite"]');
    await waitFor(() => expect(live).toHaveTextContent('Recommending MVP features: running'));
  });
});

describe('Results tabs: seven of them', () => {
  it('lists the seven tabs in the planned order', async () => {
    server.use(show(DONE));
    open();

    await screen.findByRole('tab', { name: 'Overview' });
    expect(screen.getAllByRole('tab').map((tab) => tab.textContent)).toEqual(SEVEN);
    expect(TABS.map((tab) => tab.label)).toEqual(SEVEN);
    expect(screen.getByText(/7 sections are available/i)).toBeInTheDocument();
  });

  it('moves through all seven with the arrow keys, wrapping at both ends, with one tab tabbable', async () => {
    server.use(show(DONE), metaWithStrategy(), chatThreadOk(() => EMPTY_THREAD));
    const user = userEvent.setup();
    open();

    (await screen.findByRole('tab', { name: 'Overview' })).focus();
    for (const label of [...SEVEN.slice(1), 'Overview']) {
      await user.keyboard('{ArrowRight}');
      const tab = screen.getByRole('tab', { name: label });
      expect(tab).toHaveAttribute('aria-selected', 'true');
      expect(tab).toHaveFocus();
      expect(document.querySelectorAll('[role=tab][tabindex="0"]')).toHaveLength(1);
      expect(screen.getByRole('tabpanel')).toHaveAttribute('aria-labelledby', tab.id);
    }

    await user.keyboard('{ArrowLeft}');
    expect(screen.getByRole('tab', { name: 'Run details' })).toHaveAttribute('aria-selected', 'true');
    expect(document.querySelectorAll('[role=tab][tabindex="0"]')).toHaveLength(1);
  });

  it('scrolls the tab row inside its own container', async () => {
    server.use(show(DONE));
    open();

    const list = await screen.findByRole('tablist');
    expect(list).toHaveClass('overflow-x-auto', 'min-w-0');
  });

  it('opens the Strategy tab and the Advisor tab', async () => {
    server.use(show(DONE), metaWithStrategy(), chatThreadOk(() => EMPTY_THREAD));
    const user = userEvent.setup();
    open();

    await user.click(await screen.findByRole('tab', { name: 'Strategy' }));
    expect(screen.getByRole('tabpanel')).toHaveTextContent('No strategy yet.');

    await user.click(screen.getByRole('tab', { name: 'Advisor' }));
    await waitFor(() =>
      expect(screen.getByRole('tabpanel')).toHaveTextContent('Ask about your market, competitors, risks, MVP or launch plan.'),
    );
  });
});

describe('Edit and re-run: constraints', () => {
  function FormProbe() {
    const location = useLocation();
    const state = location.state as { prefill?: unknown; constraints?: unknown } | null;
    return <p>Carried: {JSON.stringify(state?.constraints ?? 'nothing')}</p>;
  }

  function openWithForm() {
    return renderWithApp(
      <Routes>
        <Route path="/" element={<FormProbe />} />
        <Route path="/runs/:runId" element={<RunPage />} />
      </Routes>,
      { route: '/runs/run-123' },
    );
  }

  it('carries the stored constraints back to the form', async () => {
    server.use(show(STRATEGY_DONE));
    const user = userEvent.setup();
    openWithForm();

    await user.click(await screen.findByRole('button', { name: /edit and re-run/i }));

    expect(await screen.findByText(/carried/i)).toHaveTextContent(
      'Carried: {"team_size":2,"months_to_mvp":4,"budget_level":"bootstrapped","technical_skill":null,"launch_region":null}',
    );
  });

  it('carries null when the run had none', async () => {
    server.use(show({ ...DONE, constraints: null }));
    const user = userEvent.setup();
    openWithForm();

    await user.click(await screen.findByRole('button', { name: /edit and re-run/i }));

    expect(await screen.findByText(/carried/i)).toHaveTextContent('Carried: "nothing"');
  });
});

describe('Polling after a strategy request', () => {
  function Probe() {
    const { runId } = useParams();
    const run = useRun(runId);
    const generate = useGenerateStrategy(runId);
    return (
      <div>
        <p>
          State: {run.data?.state ?? 'none'}, stages: {run.data?.stages.length ?? 0}
        </p>
        <button type="button" onClick={() => generate.mutate({})}>
          Generate
        </button>
      </div>
    );
  }

  it('stays quiet on a finished run, then polls again until the strategy job ends', async () => {
    let reads = 0;
    let started = false;
    let readsAfterStart = 0;
    const bodies: unknown[] = [];
    server.use(
      http.get(runUrl(), () => {
        reads += 1;
        if (!started) {
          return HttpResponse.json(DONE);
        }
        readsAfterStart += 1;
        return HttpResponse.json(readsAfterStart < 3 ? STRATEGY_RUNNING : STRATEGY_DONE);
      }),
      strategyOk((body) => {
        bodies.push(body);
        started = true;
      }),
    );
    const user = userEvent.setup();
    renderWithApp(
      <Routes>
        <Route path="/runs/:runId" element={<Probe />} />
      </Routes>,
      { route: '/runs/run-123' },
    );

    expect(await screen.findByText('State: done, stages: 4')).toBeInTheDocument();
    await new Promise((resolve) => setTimeout(resolve, 2000));
    expect(reads).toBe(1);

    await user.click(screen.getByRole('button', { name: 'Generate' }));

    await waitFor(() => expect(bodies).toEqual([{ mode: 'missing' }]));
    expect(await screen.findByText('State: running, stages: 7')).toBeInTheDocument();
    expect(await screen.findByText('State: done, stages: 7', {}, { timeout: 8000 })).toBeInTheDocument();
    const finished = reads;
    await new Promise((resolve) => setTimeout(resolve, 2500));
    expect(reads).toBe(finished);
    expect(readsAfterStart).toBeGreaterThanOrEqual(3);
  }, 20000);

  it('sends the mode and the constraints it is given', async () => {
    const bodies: unknown[] = [];
    server.use(show(DONE), strategyOk((body) => bodies.push(body)));
    function AllProbe() {
      const generate = useGenerateStrategy('run-123');
      return (
        <button type="button" onClick={() => generate.mutate({ mode: 'all', constraints: { team_size: 4 } })}>
          Regenerate
        </button>
      );
    }
    const user = userEvent.setup();
    renderWithApp(<AllProbe />);

    await user.click(screen.getByRole('button', { name: 'Regenerate' }));

    await waitFor(() => expect(bodies).toEqual([{ mode: 'all', constraints: { team_size: 4 } }]));
  });
});
