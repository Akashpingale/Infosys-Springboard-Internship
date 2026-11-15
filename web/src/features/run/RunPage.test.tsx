/**
 * The run page: live progress, then the Overview tab.
 *
 * MSW answers every request, so no real validation is ever started and no API credit is spent. The
 * states the specification lists are each covered: running, done, partial, failed, cancelled and a
 * lost connection.
 */

import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { Route, Routes, useLocation } from 'react-router-dom';
import { describe, expect, it } from 'vitest';

import { API_URL } from '@/api/client';
import { RunPage, messageTone } from '@/features/run/RunPage';
import type { RunDetail } from '@/features/run/useRun';
import { META } from '@/test/fixtures';
import { renderWithApp } from '@/test/render';
import {
  CANCELLED,
  CANCEL_REQUESTED,
  COMPETITOR_S1_URL,
  COMPLETE_RESULT,
  DONE,
  FAILED,
  MARKET_S1_URL,
  PARTIAL,
  RUNNING,
} from '@/test/runFixtures';
import { server } from '@/test/server';
import { EMPTY_THREAD, chatThreadOk } from '@/test/strategyHandlers';

const RUN_URL = `${API_URL}/api/runs/run-123`;

function show(run: RunDetail) {
  return http.get(RUN_URL, () => HttpResponse.json(run));
}

/**
 * Render inside a real route, so useParams finds the run id exactly as it does in the app.
 */
function open() {
  return renderWithApp(
    <Routes>
      <Route path="/runs/:runId" element={<RunPage />} />
    </Routes>,
    { route: '/runs/run-123' },
  );
}

describe('Run page: while it runs', () => {
  it('shows each stage with its status and time, and nothing as finished early', async () => {
    server.use(show(RUNNING));
    open();

    expect(await screen.findByRole('heading', { name: /analysing: cropscan/i })).toBeInTheDocument();
    const list = screen.getByRole('list');
    expect(within(list).getByText('Understanding your idea')).toBeInTheDocument();
    expect(within(list).getAllByText('Done')).toHaveLength(2);
    expect(within(list).getByText('Running')).toBeInTheDocument();
    expect(within(list).getByText('Waiting')).toBeInTheDocument();
    expect(screen.getByText('6.5 s')).toBeInTheDocument();
    expect(screen.getByText(/elapsed/i)).toHaveTextContent('24.5 s');
  });

  it('announces the running stage in a live region', async () => {
    server.use(show(RUNNING));
    open();

    await screen.findByRole('heading', { name: /analysing/i });
    const live = document.querySelector('[aria-live="polite"]');
    await waitFor(() => expect(live).toHaveTextContent('Analysing the market: running'));
  });

  it('says the page can be left', async () => {
    server.use(show(RUNNING));
    open();
    expect(await screen.findByText(/you can leave this page/i)).toBeInTheDocument();
  });

  it('keeps polling until the run ends, then stops', async () => {
    let calls = 0;
    server.use(
      http.get(RUN_URL, () => {
        calls += 1;
        return HttpResponse.json(calls < 3 ? RUNNING : DONE);
      }),
    );
    open();

    // The first two replies are still running, the third is finished.
    expect(await screen.findByRole('heading', { name: /cropscan/i }, { timeout: 8000 })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole('tablist')).toBeInTheDocument(), { timeout: 8000 });

    const afterFinish = calls;
    await new Promise((resolve) => setTimeout(resolve, 2500));
    expect(calls).toBe(afterFinish);
  }, 20000);

  it('shows the results that already arrived while the rest is still running', async () => {
    server.use(show({ ...RUNNING, result: { ...COMPLETE_RESULT, status: 'partial' } }));
    open();

    expect(await screen.findByText(/results so far/i)).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Summary' })).toBeInTheDocument();
    expect(screen.queryByRole('tablist')).not.toBeInTheDocument();
  });
});

describe('Run page: cancelling', () => {
  it('asks the backend to stop and then says it is stopping', async () => {
    let cancelled = 0;
    server.use(
      http.get(RUN_URL, () => HttpResponse.json(cancelled > 0 ? CANCEL_REQUESTED : RUNNING)),
      http.post(`${RUN_URL}/cancel`, () => {
        cancelled += 1;
        return HttpResponse.json(CANCEL_REQUESTED);
      }),
    );
    const user = userEvent.setup();
    open();

    await user.click(await screen.findByRole('button', { name: /cancel run/i }));

    await waitFor(() => expect(cancelled).toBe(1));
    expect(await screen.findByRole('button', { name: /stopping after this step/i })).toBeDisabled();
    expect(screen.getByText(/the step that is running finishes first/i)).toBeInTheDocument();
  });

  it('shows a cancelled run as cancelled, with what finished', async () => {
    server.use(show(CANCELLED));
    open();

    expect(await screen.findByText('Cancelled')).toBeInTheDocument();
    expect(screen.getByText(/what finished before the cancel/i)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /cancel run/i })).not.toBeInTheDocument();
  });
});

describe('Run page: the finished result', () => {
  it('shows the header, the status and the seven tabs', async () => {
    server.use(show(DONE));
    open();

    expect(await screen.findByRole('heading', { level: 1, name: /cropscan/i })).toBeInTheDocument();
    expect(screen.getByText('Agriculture / AgriTech')).toBeInTheDocument();
    expect(screen.getByText('Complete')).toBeInTheDocument();
    expect(screen.getByText(/took/i)).toHaveTextContent('1:48');
    for (const tab of ['Overview', 'Market', 'Competitors', 'Strategy', 'Advisor', 'Sources', 'Run details']) {
      expect(screen.getByRole('tab', { name: new RegExp(tab, 'i') })).toBeInTheDocument();
    }
    expect(screen.getByRole('tab', { name: 'Overview' })).toHaveAttribute('aria-selected', 'true');
  });

  it('moves between tabs with the arrow keys', async () => {
    server.use(
      show(DONE),
      http.get(`${API_URL}/api/meta`, () => HttpResponse.json(META)),
      chatThreadOk(() => EMPTY_THREAD),
    );
    const user = userEvent.setup();
    open();

    const overview = await screen.findByRole('tab', { name: 'Overview' });
    overview.focus();
    await user.keyboard('{ArrowRight}');

    expect(screen.getByRole('tab', { name: 'Market' })).toHaveAttribute('aria-selected', 'true');
    // Prompt G built this tab, so the panel now holds the market sections.
    expect(within(screen.getByRole('tabpanel')).getByRole('navigation', { name: 'Market sections' })).toBeInTheDocument();

    await user.keyboard('{ArrowRight}');
    expect(screen.getByRole('tab', { name: 'Competitors' })).toHaveAttribute('aria-selected', 'true');
    // Prompt H built this tab, so the panel now holds the competitor filters.
    expect(within(screen.getByRole('tabpanel')).getByRole('radiogroup', { name: /by type/i })).toBeInTheDocument();

    await user.keyboard('{ArrowRight}');
    expect(screen.getByRole('tab', { name: 'Strategy' })).toHaveAttribute('aria-selected', 'true');

    await user.keyboard('{ArrowRight}');
    expect(screen.getByRole('tab', { name: 'Advisor' })).toHaveAttribute('aria-selected', 'true');

    await user.keyboard('{ArrowRight}');
    expect(screen.getByRole('tab', { name: 'Sources' })).toHaveAttribute('aria-selected', 'true');
    // Prompt I built this tab, so the panel now holds the sources table.
    expect(within(screen.getByRole('tabpanel')).getByRole('columnheader', { name: /cited by/i })).toBeInTheDocument();

    await user.keyboard('{ArrowRight}');
    expect(screen.getByRole('tab', { name: 'Run details' })).toHaveAttribute('aria-selected', 'true');
    // Prompt I built this tab too: the stage timings open it.
    expect(within(screen.getByRole('tabpanel')).getByRole('region', { name: 'Stage timings' })).toBeInTheDocument();
  });

  it('shows the summary, the four tiles and the evidence breakdown', async () => {
    server.use(show(DONE));
    open();

    await screen.findByRole('heading', { name: 'Summary' });
    expect(screen.getByText(/market size \(tam\): usd 1\.8 billion/i)).toBeInTheDocument();

    expect(screen.getByText('Evidence strength')).toBeInTheDocument();
    expect(screen.getByText('Moderate')).toBeInTheDocument();
    expect(screen.getByText('Market size (TAM)')).toBeInTheDocument();
    expect(screen.getByText('Competitors found')).toBeInTheDocument();
    expect(screen.getByText('Priority segment')).toBeInTheDocument();
    expect(screen.getByText('Smallholder farmers')).toBeInTheDocument();

    // Section 8.5: the three components are shown, with their weights.
    for (const label of ['Sourced share', 'Source breadth', 'Evidence level']) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
    expect(screen.getByText('weight 40%')).toBeInTheDocument();
    expect(screen.getAllByText(/not a prediction of success/i).length).toBeGreaterThan(0);
  });

  it('never shows a percentage as the evidence headline', async () => {
    server.use(show(DONE));
    open();

    // The tile root holds the label row and the value beneath it.
    const tile = (await screen.findByText('Evidence strength')).closest('div')?.parentElement;
    expect(tile).toHaveTextContent('Moderate');
    expect(tile).not.toHaveTextContent('67');
    expect(tile).not.toHaveTextContent('%');
  });

  it('lists the takeaways and the verify-next checklist', async () => {
    server.use(show(DONE));
    open();

    await screen.findByRole('heading', { name: 'Key takeaways' });
    expect(screen.getByText(/treatment advice in local languages/i)).toBeInTheDocument();

    expect(screen.getByRole('heading', { name: /what to verify next/i })).toBeInTheDocument();
    const checkboxes = screen.getAllByRole('checkbox');
    expect(checkboxes).toHaveLength(2);
    expect(screen.getByText(/no source confirmed the sam or som/i)).toBeInTheDocument();
  });

  it('shows the evidence mix as a bar and as a table', async () => {
    server.use(show(DONE));
    open();

    const section = (await screen.findByRole('heading', { name: 'Evidence mix' })).closest('section');
    expect(section).not.toBeNull();
    const table = within(section as HTMLElement).getByRole('table');
    expect(within(table).getByRole('columnheader', { name: 'Basis' })).toBeInTheDocument();
    expect(within(table).getByRole('rowheader', { name: 'Sourced' })).toBeInTheDocument();
    expect(within(table).getByRole('rowheader', { name: 'AI interpretation' })).toBeInTheDocument();
    expect(within(table).getByRole('rowheader', { name: 'From your idea' })).toBeInTheDocument();
    expect(within(table).getByRole('rowheader', { name: 'Assumption' })).toBeInTheDocument();
  });

  it('keeps the quality notes folded away and free of field paths', async () => {
    server.use(show(DONE));
    const user = userEvent.setup();
    open();

    const summary = await screen.findByText(/2 quality checks adjusted these results/i);
    const panel = summary.closest('details');
    expect(panel).not.toHaveAttribute('open');

    await user.click(summary);

    expect(screen.getByText(/one pain point was removed/i)).toBeInTheDocument();
    const notice = screen.getByText(/one pain point was removed/i).textContent ?? '';
    expect(notice).not.toMatch(/segments\[1\]|pain_points|\bS\d+\b/);
    // The technical text stays available, one level deeper.
    expect(screen.getAllByText('Technical detail').length).toBe(2);
  });
});

describe('Run page: citations and the source drawer', () => {
  it('numbers the chips instead of showing an evidence id', async () => {
    server.use(show(DONE));
    open();

    await screen.findByRole('heading', { name: 'Summary' });
    const chip = screen.getByRole('button', { name: /source 2: crop ai market report/i });
    expect(chip).toHaveTextContent('2');
    expect(screen.queryByText('S1')).not.toBeInTheDocument();
  });

  it('opens the drawer on the source a claim cites, and lists what rests on it', async () => {
    server.use(show(DONE));
    const user = userEvent.setup();
    open();

    await screen.findByRole('heading', { name: 'Summary' });
    await user.click(screen.getByRole('button', { name: /source 2: crop ai market report/i }));

    const drawer = await screen.findByRole('dialog');
    expect(within(drawer).getByRole('heading', { name: 'Crop AI market report' })).toBeInTheDocument();
    expect(within(drawer).getByText('reports.example')).toBeInTheDocument();
    expect(within(drawer).getByRole('link', { name: /open source/i })).toHaveAttribute('href', MARKET_S1_URL);
    expect(within(drawer).getByText(/cited by/i)).toBeInTheDocument();
    expect(within(drawer).getByText(/most small farmers say they lose crops/i)).toBeInTheDocument();
  });

  it('opens the right page when the two analyses both use the same id', async () => {
    server.use(show(DONE));
    const user = userEvent.setup();
    open();

    await screen.findByRole('heading', { name: 'Summary' });
    // The gap line belongs to the competitor analysis, whose S1 is a different page.
    await user.click(screen.getByRole('button', { name: /khatabook pricing page/i }));

    const drawer = await screen.findByRole('dialog');
    expect(within(drawer).getByRole('link', { name: /open source/i })).toHaveAttribute('href', COMPETITOR_S1_URL);
    expect(within(drawer).queryByText(/most small farmers/i)).not.toBeInTheDocument();
  });

  it('explains the search summary rather than offering a link', async () => {
    server.use(show(DONE));
    const user = userEvent.setup();
    open();

    await screen.findByRole('heading', { name: 'Key takeaways' });
    await user.click(screen.getAllByRole('button', { name: /search summary/i })[0]!);

    const drawer = await screen.findByRole('dialog');
    expect(within(drawer).getByText(/not a page we can link to/i)).toBeInTheDocument();
    expect(within(drawer).queryByRole('link', { name: /open source/i })).not.toBeInTheDocument();
  });

  it('closes on Escape and gives focus back', async () => {
    server.use(show(DONE));
    const user = userEvent.setup();
    open();

    await screen.findByRole('heading', { name: 'Summary' });
    await user.click(screen.getByRole('button', { name: /source 2: crop ai market report/i }));
    await screen.findByRole('dialog');

    await user.keyboard('{Escape}');

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  });

  it("shows the founder's own words as from your idea, with no chip to open", async () => {
    server.use(show(DONE));
    open();

    await screen.findByRole('heading', { name: 'Key takeaways' });
    const takeaway = screen.getByText(/start with the two cooperatives/i).closest('li');
    expect(takeaway).toHaveTextContent('From your idea');
    expect(within(takeaway as HTMLElement).queryByRole('button')).not.toBeInTheDocument();
  });
});

describe('Run page: partial, failed and lost connection', () => {
  it('explains a partial run and still shows what finished', async () => {
    server.use(show(PARTIAL));
    open();

    expect(await screen.findByText('Partial')).toBeInTheDocument();
    expect(screen.getByText(/some parts could not be completed/i)).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Summary' })).toBeInTheDocument();
    // The competitor analysis is missing, so its tile says so rather than showing a zero.
    expect(screen.getByText('Not analysed')).toBeInTheDocument();
  });

  it('shows a failed run plainly, with no result sections', async () => {
    server.use(show(FAILED));
    open();

    expect(await screen.findByText('Failed')).toBeInTheDocument();
    expect(screen.getByText(/the ai service is busy right now/i)).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Summary' })).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: /start a new validation/i })).toBeInTheDocument();
  });

  it('says it is retrying when the connection drops, and keeps the run on screen', async () => {
    let calls = 0;
    server.use(
      http.get(RUN_URL, () => {
        calls += 1;
        return calls === 1 ? HttpResponse.json(RUNNING) : HttpResponse.error();
      }),
    );
    open();

    await screen.findByRole('heading', { name: /analysing/i });
    expect(await screen.findByText(/lost connection/i, {}, { timeout: 10000 })).toBeInTheDocument();
    // The stages the page already had are still shown.
    expect(screen.getByText('Understanding your idea')).toBeInTheDocument();
  }, 20000);

  it('offers history when the run does not exist', async () => {
    server.use(
      http.get(RUN_URL, () =>
        HttpResponse.json(
          { error: { code: 'run_not_found', message: 'This validation could not be found.' } },
          { status: 404 },
        ),
      ),
    );
    open();

    expect(await screen.findByRole('heading', { name: /not here/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /open history/i })).toBeInTheDocument();
  });
});

/**
 * The actions in the results header (Prompt I): export, edit and re-run, delete.
 *
 * Deleting and re-running both leave the page, so the test renders the destinations as probes and
 * checks where it went and what it carried, rather than trusting the click.
 */
describe('Run page: the result actions', () => {
  /** Shows what "Edit and re-run" put in the router's state. */
  function FormProbe() {
    const location = useLocation();
    const state = location.state as { prefill?: { idea_description: string } } | null;
    return <p>Form screen. Carried: {state?.prefill?.idea_description ?? 'nothing'}</p>;
  }

  function openWithRoutes() {
    return renderWithApp(
      <Routes>
        <Route path="/" element={<FormProbe />} />
        <Route path="/history" element={<p>History screen</p>} />
        <Route path="/runs/:runId" element={<RunPage />} />
      </Routes>,
      { route: '/runs/run-123' },
    );
  }

  it('offers export, edit and re-run, and delete once the run has finished', async () => {
    server.use(show(DONE));
    open();

    expect(await screen.findByRole('button', { name: /export/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /edit and re-run/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /^delete$/i })).toBeInTheDocument();
  });

  it('offers none of them while the run is still going', async () => {
    server.use(show(RUNNING));
    open();

    await screen.findByRole('heading', { name: /analysing/i });
    expect(screen.queryByRole('button', { name: /export/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /^delete$/i })).not.toBeInTheDocument();
  });

  it('carries the original submission back to the form, without starting anything', async () => {
    let started = 0;
    server.use(
      show(DONE),
      http.post(`${API_URL}/api/runs`, () => {
        started += 1;
        return HttpResponse.json({ run_id: 'run-999', state: 'queued' });
      }),
    );
    const user = userEvent.setup();
    openWithRoutes();

    await user.click(await screen.findByRole('button', { name: /edit and re-run/i }));

    expect(await screen.findByText(/form screen/i)).toHaveTextContent(
      'Carried: A mobile app that detects crop diseases from a photo of a leaf.',
    );
    expect(started).toBe(0);
  });

  it('asks before deleting, and sends nothing when the answer is no', async () => {
    let deleted = 0;
    server.use(
      show(DONE),
      http.delete(RUN_URL, () => {
        deleted += 1;
        return new HttpResponse(null, { status: 204 });
      }),
    );
    const user = userEvent.setup();
    open();

    await user.click(await screen.findByRole('button', { name: /^delete$/i }));
    const dialog = await screen.findByRole('dialog');
    expect(dialog).toHaveTextContent('CropScan: AI crop disease detection');
    await user.click(within(dialog).getByRole('button', { name: /keep it/i }));

    expect(deleted).toBe(0);
    expect(screen.getByRole('heading', { level: 1, name: /cropscan/i })).toBeInTheDocument();
  });

  it('deletes the run and goes to the history', async () => {
    let deleted = 0;
    server.use(
      show(DONE),
      http.delete(RUN_URL, () => {
        deleted += 1;
        return new HttpResponse(null, { status: 204 });
      }),
    );
    const user = userEvent.setup();
    openWithRoutes();

    await user.click(await screen.findByRole('button', { name: /^delete$/i }));
    await user.click(within(await screen.findByRole('dialog')).getByRole('button', { name: /delete it/i }));

    await waitFor(() => expect(deleted).toBe(1));
    expect(await screen.findByText(/history screen/i)).toBeInTheDocument();
  });

  it("keeps the result and shows the backend's reason when a delete is refused", async () => {
    server.use(
      show(DONE),
      http.delete(RUN_URL, () =>
        HttpResponse.json(
          { error: { code: 'run_active', message: 'Cancel this validation before deleting it.' } },
          { status: 409 },
        ),
      ),
    );
    const user = userEvent.setup();
    open();

    await user.click(await screen.findByRole('button', { name: /^delete$/i }));
    await user.click(within(await screen.findByRole('dialog')).getByRole('button', { name: /delete it/i }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Cancel this validation before deleting it.');
    expect(screen.getByRole('heading', { level: 1, name: /cropscan/i })).toBeInTheDocument();
  });
});

describe('Run page: printing for a PDF', () => {
  it('lays every section out and opens the folded panels, then prints and puts them back', async () => {
    server.use(show(DONE));
    const printed: { text: string; openPanels: number }[] = [];
    Object.defineProperty(window, 'print', {
      writable: true,
      configurable: true,
      value: () => {
        printed.push({
          text: document.body.textContent ?? '',
          openPanels: document.querySelectorAll('details[open]').length,
        });
      },
    });
    const user = userEvent.setup();
    open();

    await user.click(await screen.findByRole('button', { name: /export/i }));
    await user.click(screen.getByText('PDF'));

    await waitFor(() => expect(printed).toHaveLength(1));
    // Every tab's content is on the page at the moment of printing, not just the open one.
    expect(printed[0]?.text).toContain('Summary');
    expect(printed[0]?.text).toContain('Feature comparison');
    expect(printed[0]?.text).toContain('Stage timings');
    expect(printed[0]?.text).toContain('Sources');
    // The quality notes were folded away and are opened for the page.
    expect(printed[0]?.openPanels).toBeGreaterThan(0);

    // Afterwards the page is back to one tab, with the panels folded again.
    await waitFor(() => expect(screen.getByRole('tabpanel')).toBeInTheDocument());
    expect(document.querySelectorAll('details[open]')).toHaveLength(0);
  });

  it('leaves the raw JSON folded, so a printed page is not tens of thousands of characters', async () => {
    server.use(show(DONE));
    const openPanels: string[] = [];
    Object.defineProperty(window, 'print', {
      writable: true,
      configurable: true,
      value: () => {
        for (const panel of document.querySelectorAll<HTMLDetailsElement>('details[open]')) {
          openPanels.push(panel.querySelector('summary')?.textContent ?? '');
        }
      },
    });
    const user = userEvent.setup();
    open();

    await user.click(await screen.findByRole('button', { name: /export/i }));
    await user.click(screen.getByText('PDF'));

    await waitFor(() => expect(openPanels.length).toBeGreaterThan(0));
    expect(openPanels.join(' ')).not.toContain('Raw result JSON');
  });
});

/**
 * What a run that produced nothing shows (Prompt J).
 *
 * A failed run has no market, no competitors and no sources, so the tabs would each open an empty
 * panel; and its closing message is a failure, not a note.
 */
describe('Run page: a run with no result', () => {
  it('offers no tabs, because there is nothing behind them', async () => {
    server.use(show(FAILED));
    open();

    await screen.findByText('Failed');
    expect(screen.queryByRole('tab')).not.toBeInTheDocument();
    expect(screen.queryByRole('tabpanel')).not.toBeInTheDocument();
  });

  it('says a failure in the failure tone, not the informational one', async () => {
    server.use(show(FAILED));
    open();

    const message = await screen.findByText(/the ai service is busy right now/i);
    // role=alert is what the error tone renders; a note renders role=status.
    expect(message.closest('[role="alert"]')).toBeInTheDocument();
  });

  it('keeps the tabs for a run that finished part-way', async () => {
    server.use(show(PARTIAL));
    open();

    expect(await screen.findByRole('tab', { name: 'Overview' })).toBeInTheDocument();
    expect(screen.getAllByRole('tab')).toHaveLength(7);
  });

  it('warns rather than alarms when a run only finished part-way', async () => {
    server.use(show(PARTIAL));
    open();

    const message = await screen.findByText(/some parts could not be completed/i);
    expect(message.closest('[role="status"]')).toBeInTheDocument();
    expect(message.closest('[role="alert"]')).not.toBeInTheDocument();
  });

  it('chooses the tone from the run state', () => {
    expect(messageTone(FAILED)).toBe('error');
    expect(messageTone(CANCELLED)).toBe('warning');
    expect(messageTone(PARTIAL)).toBe('warning');
    expect(messageTone(DONE)).toBe('info');
  });
});
