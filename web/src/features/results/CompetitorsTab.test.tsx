/**
 * The Competitors tab (KIRO_UI_UPGRADE_SPEC.md Prompt H).
 *
 * The main fixture is the saved live result docs/test_runs_m2/fintech_cashflow.json from the
 * 27 October run, read as test data only (src/test/liveFintech.json), made with the backend's own
 * code and no API call. It has all three competitor types, a competitor the founder named, a
 * verified website, sourced prices, a price marked sourced with no figure, and an eight-feature
 * comparison. The agritech run covers the single-competitor case. Small edited copies cover what
 * neither run produced.
 */

import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { Route, Routes } from 'react-router-dom';
import { describe, expect, it } from 'vitest';

import { API_URL } from '@/api/client';
import { RunPage } from '@/features/run/RunPage';
import type { RunDetail } from '@/features/run/useRun';
import { CELL } from '@/features/results/ComparisonMatrix';
import { CompetitorsTab } from '@/features/results/CompetitorsTab';
import { sortCoverage } from '@/features/results/FeatureCoverage';
import { MESSAGES, MISSING } from '@/lib/format';
import { buildSourceIndex } from '@/lib/results';
import agritech from '@/test/liveAgritech.json';
import fintech from '@/test/liveFintech.json';
import { renderWithApp } from '@/test/render';
import { server } from '@/test/server';

const LIVE = fintech as unknown as RunDetail;
const RESULT = LIVE.result!;
const ANALYSIS = RESULT.competitors!;

function renderTab(result = RESULT) {
  const sources = buildSourceIndex(result);
  const opened: string[] = [];
  const view = renderWithApp(<CompetitorsTab result={result} sources={sources} onOpenSource={(key) => opened.push(key)} />);
  return { ...view, opened };
}

function card(name: string) {
  return screen.getByRole('article', { name });
}

describe('Competitors tab: the saved live fintech result', () => {
  it('starts from the saved run, so the tests check real pipeline output', () => {
    expect(LIVE.title).toBe('Cash-flow and Expense Management Platform for Small Businesses');
    expect(ANALYSIS.competitors.map((entry) => entry.name)).toEqual([
      'Khatabook',
      'QuickBooks',
      'Xero',
      'spreadsheets',
      'CapitalOS',
    ]);
  });

  it('offers filter chips with counts taken from the competitors kept', () => {
    renderTab();
    const filters = screen.getByRole('radiogroup', { name: /show competitors by type/i });

    // Anchored, because "Indirect" contains "direct".
    expect(within(filters).getByRole('radio', { name: /^all/i })).toHaveTextContent('5');
    expect(within(filters).getByRole('radio', { name: /^direct/i })).toHaveTextContent('3');
    expect(within(filters).getByRole('radio', { name: /^indirect/i })).toHaveTextContent('1');
    expect(within(filters).getByRole('radio', { name: /^emerging/i })).toHaveTextContent('1');
    expect(within(filters).getByRole('radio', { name: /^all/i })).toHaveAttribute('aria-checked', 'true');
  });

  it('filters the cards by type and announces how many are shown', async () => {
    const user = userEvent.setup();
    renderTab();

    expect(screen.getAllByRole('article', { name: /khatabook|quickbooks|xero|spreadsheets|capitalos/i })).toHaveLength(5);

    await user.click(screen.getByRole('radio', { name: /^indirect/i }));

    expect(screen.getByRole('radio', { name: /^indirect/i })).toHaveAttribute('aria-checked', 'true');
    expect(card('spreadsheets')).toBeInTheDocument();
    expect(screen.queryByRole('article', { name: 'Khatabook' })).not.toBeInTheDocument();
    expect(screen.getByText('Showing 1 competitor.')).toBeInTheDocument();

    await user.click(screen.getByRole('radio', { name: /^all/i }));
    expect(screen.getByText('Showing 5 competitors.')).toBeInTheDocument();
  });

  it('keeps the fields of every card in the same order', () => {
    renderTab();
    for (const name of ['Khatabook', 'Xero', 'CapitalOS']) {
      // The first list holds the fixed fields; a second one, folded away, holds the extras.
      const main = card(name).querySelector('dl')!;
      const terms = within(main as HTMLElement)
        .getAllByRole('term')
        .map((term) => term.textContent);
      expect(terms).toEqual(['Website', 'Offering', 'Target', 'Key features', 'Pricing']);
    }
  });

  it('shows the type of each competitor in words', () => {
    renderTab();
    expect(within(card('Khatabook')).getByText('Direct')).toBeInTheDocument();
    expect(within(card('spreadsheets')).getByText('Indirect')).toBeInTheDocument();
    expect(within(card('CapitalOS')).getByText('Emerging')).toBeInTheDocument();
  });

  it('marks the competitor the founder named, and says where it came from', () => {
    renderTab();
    const khatabook = card('Khatabook');

    expect(within(khatabook).getByText('From your idea')).toBeInTheDocument();
    expect(within(card('Xero')).queryByText('From your idea')).not.toBeInTheDocument();
  });

  it('links a verified website and shows a dash with a reason for the rest', () => {
    renderTab();

    const link = within(card('QuickBooks')).getByRole('link', { name: /quickbooks\.intuit\.com/i });
    expect(link).toHaveAttribute('href', 'https://quickbooks.intuit.com/desktop/enterprise/pricing');
    expect(link).toHaveAttribute('rel', expect.stringContaining('noopener'));

    const xero = card('Xero');
    expect(within(xero).queryByRole('link', { name: /xero/i })).not.toBeInTheDocument();
    expect(within(xero).getByTitle(MISSING.websiteHint)).toBeInTheDocument();
  });

  it('shows a sourced price with its chip, and never a price the sources did not give', () => {
    renderTab();

    const xero = card('Xero');
    expect(within(xero).getByText('$29 - $49 per month')).toBeInTheDocument();

    // QuickBooks is marked sourced but carries no figure: shown as not found, not as a blank price.
    expect(within(card('QuickBooks')).getByText(MISSING.price)).toBeInTheDocument();
    expect(within(card('spreadsheets')).getByText(MISSING.price)).toBeInTheDocument();
  });

  it('lists strengths and weaknesses with their basis, and says when there are none', () => {
    renderTab();

    const xero = card('Xero');
    expect(within(xero).getByRole('heading', { name: 'Strengths' })).toBeInTheDocument();
    expect(xero.querySelectorAll('[data-claim]').length).toBe(2);

    expect(within(card('Khatabook')).getByText(MISSING.weaknesses)).toBeInTheDocument();
  });

  it('says how much detail the sources gave', () => {
    renderTab();
    expect(within(card('CapitalOS')).getByText('Little detail found')).toBeInTheDocument();
    expect(within(card('Xero')).getByText('Detail found')).toBeInTheDocument();
  });

  it('opens the source a competitor rests on', async () => {
    const user = userEvent.setup();
    const { opened } = renderTab();

    const chips = within(card('QuickBooks')).getAllByRole('button', { name: /open the source details/i });
    await user.click(chips[chips.length - 1]!);

    expect(opened).toHaveLength(1);
    expect(opened[0]).toMatch(/^competitors:S\d+$/);
  });

  it('folds the descriptive extras away until asked for', async () => {
    const user = userEvent.setup();
    renderTab();
    const xero = card('Xero');

    const more = within(xero).getByText(/more about xero/i);
    expect(more.closest('details')).not.toHaveAttribute('open');

    await user.click(more);
    expect(more.closest('details')).toHaveAttribute('open');
  });
});

describe('Competitors tab: the comparison matrix', () => {
  it('has one row per competitor and one column per feature, with a sticky first column', () => {
    renderTab();
    const matrix = screen.getAllByRole('table').find((element) => element.querySelector('th[scope="row"]')?.textContent === 'Khatabook');
    expect(matrix).toBeDefined();

    const headers = within(matrix!).getAllByRole('columnheader').map((cell) => cell.textContent);
    expect(headers).toEqual(['Competitor', ...(ANALYSIS.comparison.features ?? [])]);
    expect(within(matrix!).getAllByRole('rowheader')).toHaveLength((ANALYSIS.comparison.rows ?? []).length);
    expect(within(matrix!).getAllByRole('columnheader')[0]).toHaveClass('sticky');
    expect(within(matrix!).getAllByRole('rowheader')[0]).toHaveClass('sticky');
  });

  it('gives every cell a word for assistive technology, never only a symbol', () => {
    renderTab();
    const matrix = screen.getAllByRole('table').find((element) => element.querySelector('th[scope="row"]')?.textContent === 'Khatabook')!;

    const xero = within(matrix).getByRole('rowheader', { name: 'Xero' }).closest('tr')!;
    const words = within(xero)
      .getAllByRole('cell')
      .map((cell) => cell.querySelector('.sr-only')?.textContent);
    // Xero's saved row: no evidence, evidence found, then unclear, ... (see the fixture).
    expect(words.slice(0, 2)).toEqual([CELL.no_evidence_found.label, CELL.evidence_found.label]);
    expect(words.every((word) => word && word.length > 0)).toBe(true);
  });

  it('explains the symbols, and says a dash is not proof a feature is missing', () => {
    renderTab();

    const legend = screen.getByRole('list', { name: /what the symbols mean/i });
    expect(legend).toHaveTextContent('Evidence found');
    expect(legend).toHaveTextContent('Unclear');
    expect(legend).toHaveTextContent('No evidence found in the sources');
    expect(screen.getAllByText(MESSAGES.gapCaveat).length).toBeGreaterThan(0);
  });

  it('can be scrolled sideways by keyboard, and says so on a narrow screen', () => {
    renderTab();
    const region = screen.getByRole('generic', { name: /feature comparison, scrolls sideways/i });
    expect(region).toHaveAttribute('tabindex', '0');
    expect(screen.getByText('Scroll sideways to see every feature.')).toBeInTheDocument();
  });

  it('treats a cell the backend left out as unclear, never as found', () => {
    const result = {
      ...RESULT,
      competitors: {
        ...ANALYSIS,
        comparison: {
          ...ANALYSIS.comparison,
          rows: [{ competitor: 'Xero', cells: [] }],
        },
      },
    } as typeof RESULT;
    renderTab(result);

    const matrix = screen.getAllByRole('table').find((element) => element.querySelector('th[scope="row"]')?.textContent === 'Xero')!;
    const words = within(matrix)
      .getAllByRole('cell')
      .map((cell) => cell.querySelector('.sr-only')?.textContent);
    expect(new Set(words)).toEqual(new Set([CELL.unclear.label]));
  });
});

describe('Competitors tab: feature coverage', () => {
  it('sorts the features fewest first, so the gaps show at the top', () => {
    const sorted = sortCoverage(ANALYSIS.comparison.feature_coverage ?? []);
    const counts = sorted.map((entry) => entry.competitors_with_evidence);
    expect(counts).toEqual([...counts].sort((a, b) => a - b));
    expect(counts.at(-1)).toBe(2);
  });

  it('labels each bar "x of n" and repeats it as a table', () => {
    renderTab();
    const chart = screen.getByRole('region', { name: 'Feature coverage' });

    const table = within(chart).getByRole('table');
    const rows = within(table).getAllByRole('row').slice(1);
    expect(rows).toHaveLength((ANALYSIS.comparison.feature_coverage ?? []).length);
    expect(within(table).getByRole('rowheader', { name: 'Invoicing' }).closest('tr')).toHaveTextContent('2 of 5');
    expect(within(table).getByRole('rowheader', { name: 'Upcoming bill alerts' }).closest('tr')).toHaveTextContent('0 of 5');
  });

  it('uses the counts the backend computed rather than counting again', () => {
    renderTab();
    const table = within(screen.getByRole('region', { name: 'Feature coverage' })).getByRole('table');
    for (const entry of ANALYSIS.comparison.feature_coverage ?? []) {
      expect(within(table).getByRole('rowheader', { name: entry.feature }).closest('tr')).toHaveTextContent(
        `${entry.competitors_with_evidence} of ${ANALYSIS.competitors.length}`,
      );
    }
  });
});

describe('Competitors tab: gaps, differentiation and searches', () => {
  it('shows each gap as a hypothesis with its confidence and the caveat', () => {
    renderTab();
    const gaps = screen.getByRole('region', { name: 'Possible gaps' });
    const cards = within(gaps).getAllByRole('article');

    expect(cards).toHaveLength((ANALYSIS.market_gaps ?? []).length);
    for (const gapCard of cards) {
      expect(gapCard).toHaveTextContent('Hypothesis');
      expect(gapCard).toHaveTextContent(/(Low|Medium) confidence/);
      expect(gapCard).toHaveTextContent(MESSAGES.gapCaveat);
    }
    // The second saved gap names its related features, which are shown as chips.
    expect(cards[1]).toHaveTextContent('Related features');
    expect(within(cards[1]!).getByText('Weekly cash flow forecasting')).toBeInTheDocument();
  });

  it('never rates a gap above medium', () => {
    renderTab();
    expect(screen.queryByText(/high confidence/i)).not.toBeInTheDocument();
  });

  it('lists the differentiation opportunities with their basis', () => {
    renderTab();
    const section = screen.getByRole('region', { name: 'Differentiation opportunities' });
    expect(section.querySelectorAll('[data-claim]')).toHaveLength((ANALYSIS.differentiation_opportunities ?? []).length);
  });

  it('keeps the searches run folded away, with their count', async () => {
    const user = userEvent.setup();
    renderTab();
    const searches = screen.getByRole('region', { name: /searches run/i });
    const summary = within(searches).getByText(/searches run for this analysis/i);

    expect(summary.closest('details')).not.toHaveAttribute('open');
    expect(searches).toHaveTextContent(String((ANALYSIS.queries_used ?? []).length));

    await user.click(summary);
    expect(within(searches).getByText('Khatabook pricing features')).toBeInTheDocument();
  });

  it('shows the evidence notes, with any evidence id they name as a chip', () => {
    renderTab();
    const notes = screen.getByRole('region', { name: 'Evidence notes' });
    expect(notes).toHaveTextContent('The competitor evidence was rated limited.');
    expect(notes).toHaveTextContent(ANALYSIS.caveats![0]!);
  });

  it('never shows an evidence id anywhere in the tab', () => {
    const { container } = renderTab();
    expect(container.textContent).not.toMatch(/\bS\d{1,3}\b/);
  });
});

describe('Competitors tab: cases the fintech run did not produce', () => {
  it('handles the single competitor of the saved agritech run', () => {
    const result = (agritech as unknown as RunDetail).result!;
    renderTab(result);

    expect(screen.getByRole('radio', { name: /all/i })).toHaveTextContent('1');
    expect(screen.getByRole('radio', { name: /indirect/i })).toBeDisabled();
    expect(screen.getByRole('article', { name: 'Crop Doctor' })).toBeInTheDocument();
  });

  it('marks an estimated price as needing verification', () => {
    const result = {
      ...RESULT,
      competitors: {
        ...ANALYSIS,
        competitors: ANALYSIS.competitors.map((entry) =>
          entry.name === 'Xero'
            ? { ...entry, pricing_model: { value: 'About $30 a month', status: 'estimate_needs_verification', source_ids: ['S1'], note: null } }
            : entry,
        ),
      },
    } as typeof RESULT;
    renderTab(result);

    const xero = card('Xero');
    expect(within(xero).getByText('About $30 a month')).toBeInTheDocument();
    expect(within(xero).getByText('Estimate')).toBeInTheDocument();
  });

  it('says so when there is no gap and no comparison', () => {
    const result = {
      ...RESULT,
      competitors: {
        ...ANALYSIS,
        market_gaps: [],
        comparison: { features: [], rows: [], feature_coverage: [] },
      },
    } as typeof RESULT;
    renderTab(result);

    expect(screen.getAllByText('No feature comparison could be made.').length).toBeGreaterThan(0);
    expect(within(screen.getByRole('region', { name: 'Possible gaps' })).getByText(MISSING.none)).toBeInTheDocument();
  });

  it('explains a competitor stage that did not finish, with its reason', () => {
    const result = {
      ...RESULT,
      status: 'partial',
      competitors: null,
      errors: [{ stage: 'competitor_analysis', code: 'insufficient_evidence', message: 'No competitor could be confirmed from the search results.' }],
    } as typeof RESULT;
    renderTab(result);

    const alert = screen.getByRole('status');
    expect(alert).toHaveTextContent('Comparing competitors did not finish');
    expect(alert).toHaveTextContent('No competitor could be confirmed from the search results.');
  });
});

describe('Competitors tab: in the run page', () => {
  it('opens from the tab bar and opens the source drawer on a competitor source', async () => {
    server.use(http.get(`${API_URL}/api/runs/live-fintech`, () => HttpResponse.json(LIVE)));
    const user = userEvent.setup();
    renderWithApp(
      <Routes>
        <Route path="/runs/:runId" element={<RunPage />} />
      </Routes>,
      { route: '/runs/live-fintech' },
    );

    await user.click(await screen.findByRole('tab', { name: 'Competitors' }));
    const panel = screen.getByRole('tabpanel');
    const xero = within(panel).getByRole('article', { name: 'Xero' });
    const chips = within(xero).getAllByRole('button', { name: /open the source details/i });
    await user.click(chips[0]!);

    const drawer = await screen.findByRole('dialog');
    const href = within(drawer).getByRole('link', { name: /open source/i }).getAttribute('href');
    // The drawer must open one of the competitor analysis's own sources, not a market one with the same id.
    expect(ANALYSIS.sources!.map((source) => source.url)).toContain(href);
  });
});
