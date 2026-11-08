/**
 * The Run details tab (KIRO_UI_UPGRADE_SPEC.md Prompt I, Sections 7.4, 9 and 10.3).
 *
 * The fixture is the saved live fintech run (src/test/liveFintech.json), read as test data only.
 * Its four stages all finished, it made four labelled searches plus five competitor searches whose
 * result counts the pipeline does not record, and three quality checks changed something, which is
 * every case this tab has to tell apart.
 */

import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { RunDetail } from '@/features/run/useRun';
import { COPY_DONE, COPY_FAILED, RunDetailsTab } from '@/features/results/RunDetailsTab';
import { SHADES } from '@/features/results/StageTimings';
import type { PipelineResult } from '@/lib/results';
import fintech from '@/test/liveFintech.json';
import { renderWithApp } from '@/test/render';
import { FAILED, PARTIAL } from '@/test/runFixtures';

const LIVE = fintech as unknown as RunDetail;
const RESULT = LIVE.result!;

function renderTab(run: RunDetail = LIVE, result: PipelineResult = RESULT) {
  return renderWithApp(<RunDetailsTab run={run} result={result} />);
}

function section(name: RegExp | string) {
  return screen.getByRole('region', { name });
}

/** jsdom has no object URLs, so saving a file is stubbed and the call is inspected. */
let createdUrls: number;

beforeEach(() => {
  createdUrls = 0;
  Object.defineProperty(URL, 'createObjectURL', {
    writable: true,
    configurable: true,
    value: () => {
      createdUrls += 1;
      return 'blob:stub';
    },
  });
  Object.defineProperty(URL, 'revokeObjectURL', { writable: true, configurable: true, value: () => undefined });
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('Run details: stage timings', () => {
  it('shows a bar and a table of the four stages', () => {
    renderTab();
    const timings = section('Stage timings');
    const table = within(timings).getByRole('table');

    expect(within(table).getAllByRole('rowheader')).toHaveLength(5);
    for (const label of [
      'Understanding your idea',
      'Searching the web',
      'Analysing the market',
      'Comparing competitors',
    ]) {
      expect(within(table).getByRole('rowheader', { name: label })).toBeInTheDocument();
    }
  });

  it('paints every segment, using a plain colour class for each step', () => {
    renderTab();

    /*
     * Tailwind emits no rule at all for something like `bg-primary/75`, because the token holds a
     * whole colour rather than channel numbers, which left three of the four segments unpainted.
     * The classes must stay plain, and every measured stage must have one.
     */
    expect(SHADES.every((shade) => !shade.includes('/'))).toBe(true);

    const bar = section('Stage timings').querySelector('[aria-hidden="true"]');
    const segments = [...(bar?.children ?? [])];
    expect(segments).toHaveLength(4);
    expect(segments.map((segment) => [...segment.classList].find((name) => name.startsWith('bg-')))).toEqual([
      ...SHADES,
    ]);
  });

  it('labels each stage with its own duration and share', () => {
    renderTab();
    const table = within(section('Stage timings')).getByRole('table');
    const row = within(table).getByRole('rowheader', { name: 'Comparing competitors' }).closest('tr');

    expect(row).toHaveTextContent('47.4 s');
    expect(row).toHaveTextContent('46%');
    expect(row).toHaveTextContent('Done');
  });

  it("states the pipeline's own total rather than adding the stages up", () => {
    renderTab();
    const timings = section('Stage timings');

    expect(within(timings).getByText(/1:42 in total, measured end to end/i)).toBeInTheDocument();
    expect(within(within(timings).getByRole('table')).getByRole('rowheader', { name: 'Total' }).closest('tr')).toHaveTextContent(
      '1:42',
    );
  });

  it('says when the total is only the stages added up', () => {
    renderTab({ ...LIVE, result: { ...RESULT, timings: {} } } as RunDetail, { ...RESULT, timings: {} });
    expect(screen.getByText(/in total, added up from the stages/i)).toBeInTheDocument();
  });

  it('gives a stage that did not run a word instead of a zero', () => {
    renderTab(FAILED, PARTIAL.result as PipelineResult);
    const table = within(section('Stage timings')).getByRole('table');
    const row = within(table).getByRole('rowheader', { name: 'Searching the web' }).closest('tr');

    expect(row).toHaveTextContent('Skipped');
    expect(row).toHaveTextContent('\u2014');
    expect(row).not.toHaveTextContent('0.0 s');
  });
});

describe('Run details: searches run', () => {
  it('groups the searches by the stage that made them', () => {
    renderTab();
    const searches = section(/searches run/i);

    expect(within(searches).getByText('Searching the web')).toBeInTheDocument();
    expect(within(searches).getByText('Comparing competitors')).toBeInTheDocument();
    expect(within(searches).getByText(/9 searches, in the order the stages made them/i)).toBeInTheDocument();
  });

  it('shows each query with its label and how many results came back', () => {
    renderTab();
    const searches = section(/searches run/i);

    expect(within(searches).getByText('Market size and trends')).toBeInTheDocument();
    expect(within(searches).getAllByText('3 results').length).toBeGreaterThanOrEqual(4);
    expect(within(searches).getByText('Khatabook pricing features')).toBeInTheDocument();
  });

  it('says a result count is unknown rather than showing none', () => {
    renderTab();
    const row = screen.getByText('Khatabook pricing features').closest('li');

    expect(row).toHaveTextContent('Results not recorded');
    expect(row).not.toHaveTextContent('0 results');
  });

  it('says plainly when a run recorded no search', () => {
    renderTab(LIVE, { ...RESULT, search: null, competitors: null } as PipelineResult);
    expect(screen.getByText(/no search was recorded for this run/i)).toBeInTheDocument();
  });

  it('reports a search that failed', () => {
    const sections = (RESULT.search?.sections ?? []).map((entry, index) =>
      index === 0 ? { ...entry, error: 'The search service timed out.', results: [] } : entry,
    );
    renderTab(LIVE, { ...RESULT, search: { ...RESULT.search!, sections } } as PipelineResult);

    expect(screen.getByText(/this search failed: the search service timed out/i)).toBeInTheDocument();
  });
});

describe('Run details: quality checks', () => {
  it('groups the notices by stage, with a count', () => {
    renderTab();
    const checks = section('Quality checks');

    expect(within(checks).getByText(/3 checks adjusted this result/i)).toBeInTheDocument();
    expect(within(checks).getByText('Analysing the market').textContent).toContain('2');
    expect(within(checks).getByText('Comparing competitors').textContent).toContain('1');
  });

  it("shows the reader's wording, with the field path kept one level down", async () => {
    const user = userEvent.setup();
    renderTab();
    const checks = section('Quality checks');

    const message = within(checks).getByText(/one demand claim quoted a figure/i);
    expect(message.textContent).not.toMatch(/demand_evidence|\[\d\]/);

    await user.click(within(checks).getAllByText('Technical detail')[0]!);
    expect(within(checks).getByText(/market_demand\.demand_evidence\[1\]/)).toBeInTheDocument();
  });

  it('names the code, so a developer can find the check', () => {
    renderTab();
    expect(within(section('Quality checks')).getAllByText('figure_unmatched')).toHaveLength(3);
  });

  it('says plainly when no check changed anything', () => {
    renderTab(LIVE, { ...RESULT, notices: [] } as PipelineResult);
    expect(screen.getByText(/nothing was removed, rewritten or left out/i)).toBeInTheDocument();
  });
});

describe('Run details: the raw JSON', () => {
  it('stays folded away until it is asked for', () => {
    renderTab();
    const summary = screen.getByText('Raw result JSON');

    expect(summary.closest('details')).not.toHaveAttribute('open');
    expect(screen.queryByRole('button', { name: /copy json/i })).not.toBeVisible();
  });

  it('shows the untouched result once opened', async () => {
    const user = userEvent.setup();
    renderTab();

    await user.click(screen.getByText('Raw result JSON'));

    const block = document.querySelector('pre');
    expect(block?.textContent).toContain('"status": "complete"');
    expect(block?.textContent).toContain('"Khatabook"');
  });

  it('copies it to the clipboard and says it did', async () => {
    const user = userEvent.setup();
    renderTab();

    await user.click(screen.getByText('Raw result JSON'));
    await user.click(screen.getByRole('button', { name: /copy json/i }));

    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent(COPY_DONE));
    expect(await navigator.clipboard.readText()).toContain('"status": "complete"');
  });

  it('points at Download when the browser will not let it copy', async () => {
    const user = userEvent.setup();
    renderTab();
    await user.click(screen.getByText('Raw result JSON'));
    vi.spyOn(navigator.clipboard, 'writeText').mockRejectedValue(new Error('denied'));

    await user.click(screen.getByRole('button', { name: /copy json/i }));

    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent(COPY_FAILED));
  });

  it('saves it as a file named after the run', async () => {
    const user = userEvent.setup();
    renderTab();

    await user.click(screen.getByText('Raw result JSON'));
    await user.click(screen.getByRole('button', { name: /download json/i }));

    expect(createdUrls).toBe(1);
    await waitFor(() =>
      expect(screen.getByRole('status')).toHaveTextContent(
        /saved as validation-cash-flow-and-expense-management-platform.*2026-10-27\.json/i,
      ),
    );
  });
});
