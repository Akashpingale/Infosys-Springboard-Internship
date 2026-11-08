/**
 * The Sources tab (KIRO_UI_UPGRADE_SPEC.md Prompt I, Sections 7.4 and 8.6).
 *
 * The main fixture is the saved live fintech run (src/test/liveFintech.json), read as test data
 * only, with no API call. It is the awkward case a sources table has to survive: 21 sources across
 * the two analyses, one page cited by both of them under different ids, and only 9 of the 21 with a
 * relevance score.
 */

import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { Route, Routes } from 'react-router-dom';
import { afterEach, describe, expect, it } from 'vitest';

import { API_URL } from '@/api/client';
import { RunPage } from '@/features/run/RunPage';
import type { RunDetail } from '@/features/run/useRun';
import { SCORE_NOTE, SourcesTab } from '@/features/results/SourcesTab';
import { buildSourceIndex, collectClaims, type PipelineResult } from '@/lib/results';
import fintech from '@/test/liveFintech.json';
import { renderWithApp } from '@/test/render';
import { COMPLETE_RESULT, DONE } from '@/test/runFixtures';
import { server } from '@/test/server';
import { NARROW } from '@/lib/useMediaQuery';

/** The setup file's stub: nothing matches, so the wide layout is the default everywhere. */
const WIDE_MATCH_MEDIA = window.matchMedia;

const LIVE = fintech as unknown as RunDetail;
const RESULT = LIVE.result!;

function renderTab(result: PipelineResult = RESULT) {
  const sources = buildSourceIndex(result);
  const opened: string[] = [];
  const view = renderWithApp(
    <SourcesTab
      result={result}
      sources={sources}
      claims={collectClaims(result)}
      onOpenSource={(key) => opened.push(key)}
    />,
  );
  return { ...view, opened };
}

/** The body rows, without the header row. */
function bodyRows(): HTMLElement[] {
  return within(screen.getByRole('table')).getAllByRole('row').slice(1);
}

function rowFor(title: string | RegExp): HTMLElement {
  return screen.getByRole('button', { name: title }).closest('tr') as HTMLElement;
}

describe('Sources tab: the table', () => {
  it('lists every source with the number its citation chips use', () => {
    renderTab();

    expect(bodyRows()).toHaveLength(21);
    expect(rowFor(/^Digital Banking Platform Market Size/)).toHaveTextContent('1');
    expect(rowFor(/^FinTech Futures/)).toHaveTextContent('13');
  });

  it('shows the domain, the analysis that cited it and the search it came from', () => {
    renderTab();
    const row = rowFor(/^Digital Banking Platform Market Size/);

    expect(row).toHaveTextContent('finance.yahoo.com');
    expect(row).toHaveTextContent('Market');
    expect(row).toHaveTextContent('Found in the Market size and trends search');
  });

  it('says how many sources the result has', () => {
    renderTab();
    expect(screen.getByRole('status')).toHaveTextContent('21 sources in this result.');
  });

  it('keeps one page as two rows when both analyses cited it', () => {
    renderTab();
    const shared = screen.getAllByRole('button', { name: /^10 Essential Small Business Systems/ });

    // The market analysis called it S4 and the competitor analysis S1. Same page, separate numbering.
    expect(shared).toHaveLength(2);
    const sections = shared.map((button) => button.closest('tr')?.textContent ?? '');
    expect(sections.some((text) => text.includes('Market'))).toBe(true);
    expect(sections.some((text) => text.includes('Competitors'))).toBe(true);
  });

  it('never shows an evidence id', () => {
    const { container } = renderTab();
    expect(container.textContent).not.toMatch(/\bS\d{1,3}\b/);
  });
});

describe('Sources tab: a value the search engine did not give', () => {
  it('shows a dash for a missing score and says so for a screen reader', () => {
    renderTab();
    const row = rowFor(/^QuickBooks Desktop Enterprise Pricing/);

    expect(within(row).getByText('No score reported')).toBeInTheDocument();
    expect(row).toHaveTextContent('\u2014');
  });

  it('shows the score the engine did give, to two places', () => {
    renderTab();
    expect(rowFor(/^FinTech Futures/)).toHaveTextContent('0.78');
  });

  it('explains that a score is the search engine\u2019s own relevance, not quality', () => {
    renderTab();
    expect(screen.getByText(SCORE_NOTE)).toBeInTheDocument();
  });

  it('every source of the saved run is cited by something, so no row reads zero', () => {
    renderTab();
    expect(screen.queryByText('Cited by nothing in this result')).not.toBeInTheDocument();
  });

  it('reads a zero out in words for a source nothing rests on', () => {
    const market = RESULT.market!;
    const withUncited = {
      ...RESULT,
      market: {
        ...market,
        sources: [
          ...(market.sources ?? []),
          { id: 'S99', title: 'Collected but never cited', url: 'https://unused.example/page' },
        ],
      },
    } as PipelineResult;
    renderTab(withUncited);

    const row = rowFor('Collected but never cited');
    expect(within(row).getByText('Cited by nothing in this result')).toBeInTheDocument();
  });

  it('gives the search summary no number, because its chip is a word', () => {
    renderTab(COMPLETE_RESULT);
    const row = rowFor('Search engine summary');

    expect(within(row).getByText(/no number: the search summary/i)).toBeInTheDocument();
    expect(row).toHaveTextContent(/own summary, not a page/i);
  });
});

describe('Sources tab: searching', () => {
  it('narrows the table and says how many are shown', async () => {
    const user = userEvent.setup();
    renderTab();

    await user.type(screen.getByRole('searchbox', { name: /search the sources/i }), 'khatabook');

    expect(bodyRows().length).toBeGreaterThan(0);
    expect(bodyRows().length).toBeLessThan(21);
    expect(screen.getByRole('status')).toHaveTextContent(`Showing ${bodyRows().length} of 21 sources.`);
  });

  it('matches the domain as well as the title', async () => {
    const user = userEvent.setup();
    renderTab();

    await user.type(screen.getByRole('searchbox', { name: /search the sources/i }), 'quickbooks.intuit.com');

    expect(bodyRows()).toHaveLength(1);
  });

  it('says plainly when nothing matches, and how to get back', async () => {
    const user = userEvent.setup();
    renderTab();

    await user.type(screen.getByRole('searchbox', { name: /search the sources/i }), 'no such page');

    expect(screen.queryByRole('table')).not.toBeInTheDocument();
    expect(screen.getByText(/no source matches .*no such page.*clear the search/i)).toBeInTheDocument();
  });
});

describe('Sources tab: sorting', () => {
  it('starts on the source number, ascending, and says so', () => {
    renderTab();
    const header = screen.getByRole('columnheader', { name: /source/i });

    expect(header).toHaveAttribute('aria-sort', 'ascending');
    expect(bodyRows()[0]).toHaveTextContent(/^1/);
  });

  it('sorts the highest score first, and keeps the unscored at the bottom', async () => {
    const user = userEvent.setup();
    renderTab();

    await user.click(screen.getByRole('button', { name: 'Score' }));

    expect(screen.getByRole('columnheader', { name: /score/i })).toHaveAttribute('aria-sort', 'descending');
    expect(bodyRows()[0]).toHaveTextContent('0.78');
    expect(within(bodyRows().at(-1) as HTMLElement).getByText('No score reported')).toBeInTheDocument();
  });

  it('turns a column around on the second click', async () => {
    const user = userEvent.setup();
    renderTab();

    await user.click(screen.getByRole('button', { name: 'Title' }));
    const first = bodyRows()[0]?.textContent ?? '';
    await user.click(screen.getByRole('button', { name: 'Title' }));

    expect(screen.getByRole('columnheader', { name: /title/i })).toHaveAttribute('aria-sort', 'descending');
    expect(bodyRows()[0]?.textContent).not.toBe(first);
  });

  it('sorts by how many findings rest on a source', async () => {
    const user = userEvent.setup();
    renderTab();

    await user.click(screen.getByRole('button', { name: /cited by/i }));

    const counts = bodyRows().map((row) => Number(row.lastElementChild?.textContent ?? '0'));
    expect(counts).toEqual([...counts].sort((a, b) => b - a));
  });

  it('marks only the column in use', async () => {
    const user = userEvent.setup();
    renderTab();

    await user.click(screen.getByRole('button', { name: 'Domain' }));

    const sorted = screen.getAllByRole('columnheader').filter((header) => header.getAttribute('aria-sort') !== 'none');
    expect(sorted).toHaveLength(1);
    expect(sorted[0]).toHaveAccessibleName(/domain/i);
  });
});

describe('Sources tab: opening a source', () => {
  it('opens the drawer from the title button', async () => {
    const user = userEvent.setup();
    const { opened } = renderTab();

    await user.click(screen.getByRole('button', { name: /^FinTech Futures/ }));

    expect(opened).toEqual(['competitors:S3']);
  });

  it('opens the drawer from anywhere in the row', async () => {
    const user = userEvent.setup();
    const { opened } = renderTab();

    await user.click(within(rowFor(/^FinTech Futures/)).getByText('fintechfutures.com'));

    expect(opened).toEqual(['competitors:S3']);
  });

  it('shows the page and what rests on it, through the real drawer', async () => {
    server.use(http.get(`${API_URL}/api/runs/run-123`, () => HttpResponse.json(DONE)));
    const user = userEvent.setup();
    renderWithApp(
      <Routes>
        <Route path="/runs/:runId" element={<RunPage />} />
      </Routes>,
      { route: '/runs/run-123' },
    );

    await user.click(await screen.findByRole('tab', { name: 'Sources' }));
    await user.click(screen.getByRole('button', { name: 'Crop AI market report' }));

    const drawer = await screen.findByRole('dialog');
    expect(within(drawer).getByRole('heading', { name: 'Crop AI market report' })).toBeInTheDocument();
    expect(within(drawer).getByText(/most small farmers say they lose crops/i)).toBeInTheDocument();
  });
});

describe('Sources tab: nothing to show', () => {
  it('says so when the result cites no source at all', () => {
    renderTab({ ...RESULT, market: null, competitors: null } as PipelineResult);

    expect(screen.queryByRole('table')).not.toBeInTheDocument();
    expect(screen.getByText(/cites no sources/i)).toBeInTheDocument();
  });
});

/**
 * The narrow layout (Prompt J). Six columns cannot be read at 390 px, so the rows become cards and
 * the column headers become sort buttons. Only one of the two layouts is ever in the document, so a
 * screen reader is not read every source twice.
 */
describe('Sources tab: on a narrow screen', () => {
  function narrow(): void {
    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      configurable: true,
      value: (query: string) => ({
        matches: query === NARROW,
        media: query,
        onchange: null,
        addEventListener: () => {},
        removeEventListener: () => {},
        dispatchEvent: () => false,
      }),
    });
  }

  afterEach(() => {
    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      configurable: true,
      value: WIDE_MATCH_MEDIA,
    });
  });

  it('shows cards instead of the table, one per source, and no duplicate rows', () => {
    narrow();
    renderTab();

    expect(screen.queryByRole('table')).not.toBeInTheDocument();
    expect(screen.getAllByRole('listitem')).toHaveLength(21);
    expect(screen.getAllByRole('button', { name: /^FinTech Futures/ })).toHaveLength(1);
  });

  it('keeps every value a row had, with its column name as the label', () => {
    narrow();
    renderTab();

    const card = screen.getByRole('button', { name: /^Digital Banking Platform Market Size/ }).closest('li')!;
    const terms = within(card).getAllByRole('term').map((term) => term.textContent);
    expect(terms).toEqual(['Domain', 'Section', 'Score', 'Cited by']);
    expect(card).toHaveTextContent('finance.yahoo.com');
    expect(card).toHaveTextContent('Market');
    expect(card).toHaveTextContent('0.55');
  });

  it('still says a missing score is missing', () => {
    narrow();
    renderTab();

    const card = screen.getByRole('button', { name: /^QuickBooks Desktop Enterprise Pricing/ }).closest('li')!;
    expect(within(card).getByText('No score reported')).toBeInTheDocument();
  });

  it('offers the same sorting as buttons, each a 44 px target', async () => {
    narrow();
    const user = userEvent.setup();
    renderTab();

    const group = screen.getByRole('group', { name: /sort the sources/i });
    const score = within(group).getByRole('button', { name: 'Score' });
    expect(score).toHaveClass('min-h-[44px]');

    await user.click(score);

    expect(score).toHaveAttribute('aria-pressed', 'true');
    const first = screen.getAllByRole('listitem')[0];
    expect(first).toHaveTextContent('0.78');
  });

  it('opens the drawer from a card', async () => {
    narrow();
    const user = userEvent.setup();
    const { opened } = renderTab();

    await user.click(screen.getByRole('button', { name: /^FinTech Futures/ }));

    expect(opened).toEqual(['competitors:S3']);
  });
});
