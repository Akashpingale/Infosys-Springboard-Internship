/**
 * The Market tab (KIRO_UI_UPGRADE_SPEC.md Prompt G).
 *
 * The main fixture is the saved live result docs/test_runs_m2/agritech.json from the 27 October
 * run, read as test data only (src/test/liveAgritech.json). It was turned into the run API's reply
 * shape with the backend's own code, and no API was called to make it. Small variations of it cover
 * the cases that run did not happen to produce: an estimate, an empty trend column, a missing
 * analysis.
 */

import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { Route, Routes } from 'react-router-dom';
import { describe, expect, it } from 'vitest';

import { API_URL } from '@/api/client';
import { RunPage } from '@/features/run/RunPage';
import type { RunDetail } from '@/features/run/useRun';
import { MSG_BROADER, MarketTab } from '@/features/results/MarketTab';
import { MESSAGES } from '@/lib/format';
import { buildSourceIndex, splitEvidenceIds } from '@/lib/results';
import live from '@/test/liveAgritech.json';
import { renderWithApp } from '@/test/render';
import { server } from '@/test/server';

const LIVE = live as unknown as RunDetail;
const RESULT = LIVE.result!;
const MARKET = RESULT.market!;

function renderTab(result = RESULT) {
  const sources = buildSourceIndex(result);
  const opened: string[] = [];
  const view = renderWithApp(<MarketTab result={result} sources={sources} onOpenSource={(key) => opened.push(key)} />);
  return { ...view, opened, sources };
}

function section(name: RegExp) {
  return screen.getByRole('region', { name });
}

describe('Market tab: the saved live agritech result', () => {
  it('starts from the saved run, so the tests check real pipeline output', () => {
    expect(LIVE.title).toBe('AI-Powered Crop Disease Detection and Treatment App for Small Farmers');
    expect(MARKET.sources).toHaveLength(10);
    expect(MARKET.market_size.tam.status).toBe('sourced');
  });

  it('lists every section in the navigation and jumps to it', async () => {
    const user = userEvent.setup();
    renderTab();

    const nav = screen.getByRole('navigation', { name: 'Market sections' });
    const links = within(nav).getAllByRole('link');
    expect(links.map((link) => link.textContent)).toEqual([
      'Industry overview',
      'Demand',
      'Market size',
      'Trends',
      'Segments',
      'Opportunities and limitations',
      'Evidence notes',
    ]);

    await user.click(within(nav).getByRole('link', { name: 'Segments' }));
    expect(document.activeElement).toBe(screen.getByRole('heading', { level: 2, name: 'Segments' }));
  });

  it('shows the industry overview with its category and developments', () => {
    renderTab();
    const overview = section(/industry overview/i);

    expect(within(overview).getByText(MARKET.industry_overview.market_category)).toBeInTheDocument();
    expect(within(overview).getByText(MARKET.industry_overview.summary)).toBeInTheDocument();
    for (const development of MARKET.industry_overview.developments ?? []) {
      expect(within(overview).getByText(development.text, { exact: false })).toBeInTheDocument();
    }
  });

  it('shows the demand evidence with a basis chip on every claim', () => {
    renderTab();
    const demand = section(/^demand$/i);

    const evidence = MARKET.market_demand.demand_evidence ?? [];
    expect(evidence.length).toBeGreaterThan(0);
    expect(within(demand).getByText(evidence[0]!.text, { exact: false })).toBeInTheDocument();

    // Every listed claim carries a basis in words (Section 6.2: never colour alone).
    const claims = demand.querySelectorAll('[data-claim]');
    expect(claims.length).toBe(
      (MARKET.market_demand.demand_evidence ?? []).length +
        (MARKET.market_demand.customer_problems ?? []).length +
        (MARKET.market_demand.interest_signals ?? []).length,
    );
    for (const claim of claims) {
      expect(claim.textContent).toMatch(/Sourced|AI interpretation|From your idea|Assumption/);
    }
  });

  it('opens the right source from a demand claim', async () => {
    const user = userEvent.setup();
    const { opened } = renderTab();
    const demand = section(/^demand$/i);

    const chip = within(demand).getAllByRole('button', { name: /open the source details/i })[0]!;
    await user.click(chip);

    expect(opened).toHaveLength(1);
    expect(opened[0]).toMatch(/^market:S\d+$/);
  });

  it('shows the TAM as sourced and the SAM and SOM as unavailable with a reason', () => {
    renderTab();
    const size = section(/market size/i);

    expect(within(size).getByText('USD 1.8 billion')).toBeInTheDocument();
    expect(within(size).getAllByText('Sourced').length).toBeGreaterThan(0);
    expect(within(size).getByText('Global AI-based crop disease detection market in 2025.')).toBeInTheDocument();

    // Section 2 finding 12: no bare "Not available"; an unavailable chip and a one-line reason.
    expect(within(size).getAllByText(MESSAGES.marketSizeUnavailable)).toHaveLength(2);
    expect(within(size).queryByText('Not available')).not.toBeInTheDocument();
  });

  it('lists the broader markets as context only, never as the TAM', () => {
    renderTab();
    const size = section(/market size/i);
    const table = within(size).getByRole('table', { name: /broader markets/i });

    expect(within(size).getByText(MSG_BROADER)).toBeInTheDocument();
    const rows = within(table).getAllByRole('row').slice(1);
    expect(rows).toHaveLength((MARKET.broader_markets ?? []).length);
    expect(within(table).getByText('USD 31.9 billion')).toBeInTheDocument();
    expect(within(table).getByText('Global Agritech market in 2025.')).toBeInTheDocument();

    // The whole-sector figure must not appear among the TAM, SAM and SOM tiles.
    const tiles = within(size).getAllByRole('heading', { level: 3, name: /^(TAM|SAM|SOM)$/ });
    for (const tile of tiles) {
      expect(tile.closest('div')?.parentElement).not.toHaveTextContent('USD 31.9 billion');
    }
  });

  it('puts the trends in four columns by category, and says when a column is empty', () => {
    renderTab();
    const trends = section(/^trends$/i);

    for (const label of ['Technology', 'Consumer', 'Industry', 'Business']) {
      expect(within(trends).getByRole('heading', { level: 3, name: label })).toBeInTheDocument();
    }
    // The saved run has no industry trend, so that column says so rather than staying blank.
    const industry = within(trends).getByRole('heading', { level: 3, name: 'Industry' }).parentElement!;
    expect(industry).toHaveTextContent('None found in the sources.');

    const technology = within(trends).getByRole('heading', { level: 3, name: 'Technology' }).parentElement!;
    expect(technology).toHaveTextContent(/precision agriculture/i);
  });

  it('shows the segments as cards with the priority one marked and its rationale and risks', () => {
    renderTab();
    const segments = section(/^segments$/i);
    const cards = within(segments).getAllByRole('article');
    expect(cards).toHaveLength(2);

    const priority = within(segments).getByRole('article', { name: 'Smallholder Farmers' });
    expect(within(priority).getByText('Priority segment')).toBeInTheDocument();
    expect(within(priority).getByText(MARKET.priority_segment!.rationale)).toBeInTheDocument();
    for (const risk of MARKET.priority_segment!.risks ?? []) {
      expect(within(priority).getByText(risk)).toBeInTheDocument();
    }

    const other = within(segments).getByRole('article', { name: 'Farming Cooperatives' });
    expect(within(other).queryByText('Priority segment')).not.toBeInTheDocument();
    expect(within(other).queryByText(/why this segment first/i)).not.toBeInTheDocument();
  });

  it('labels the segmentation basis and lists needs and pain points', () => {
    renderTab();
    const priority = within(section(/^segments$/i)).getByRole('article', { name: 'Smallholder Farmers' });

    expect(within(priority).getByText('By needs')).toBeInTheDocument();
    expect(within(priority).getByRole('heading', { name: 'Needs' })).toBeInTheDocument();
    expect(within(priority).getByRole('heading', { name: 'Pain points' })).toBeInTheDocument();
  });

  it('shows opportunities and limitations side by side', () => {
    renderTab();
    const both = section(/opportunities and limitations/i);

    expect(within(both).getByRole('heading', { level: 3, name: 'Opportunities' })).toBeInTheDocument();
    expect(within(both).getByRole('heading', { level: 3, name: 'Limitations' })).toBeInTheDocument();
    expect(both.querySelectorAll('[data-claim]')).toHaveLength(
      (MARKET.opportunities ?? []).length + (MARKET.limitations ?? []).length,
    );
  });

  it('shows the evidence notes with the ids they name as chips, not as raw ids', () => {
    renderTab();
    const notes = section(/evidence notes/i);

    expect(notes).toHaveTextContent('The market evidence was rated limited.');
    // The live note says "sources S2 and S3"; the reader sees two chips instead of the ids.
    expect(notes).toHaveTextContent(/significant discrepancy between sources/i);
    expect(within(notes).queryByText(/\bS2\b/)).not.toBeInTheDocument();
    expect(within(notes).getAllByRole('button', { name: /open the source details/i }).length).toBeGreaterThanOrEqual(2);
    expect(notes).toHaveTextContent(MARKET.caveats![0]!);
  });

  it('never shows an evidence id anywhere in the tab', () => {
    const { container } = renderTab();
    // Chips carry numbers; an "S" id would mean a reference leaked through as text.
    expect(container.textContent).not.toMatch(/\bS\d{1,3}\b/);
  });
});

describe('Market tab: cases the saved run did not produce', () => {
  it('marks an estimated figure as needing verification', () => {
    const result = {
      ...RESULT,
      market: {
        ...MARKET,
        market_size: {
          ...MARKET.market_size,
          sam: { value: 'USD 90 million', status: 'estimate_needs_verification', source_ids: ['S1'], note: 'India only.', scope: 'idea_market' },
        },
      },
    } as typeof RESULT;
    renderTab(result);
    const size = section(/market size/i);

    expect(within(size).getByText('USD 90 million')).toBeInTheDocument();
    expect(within(size).getByText('Estimate')).toBeInTheDocument();
    expect(within(size).getByText(/verify it against its source/i)).toBeInTheDocument();
  });

  it('says so when no broader-market figure was found', () => {
    renderTab({ ...RESULT, market: { ...MARKET, broader_markets: [] } } as typeof RESULT);
    expect(screen.getByText('No broader-market figures were found.')).toBeInTheDocument();
    expect(screen.queryByRole('table')).not.toBeInTheDocument();
  });

  it('says so when no priority segment was chosen, and marks no card', () => {
    renderTab({ ...RESULT, market: { ...MARKET, priority_segment: null } } as typeof RESULT);
    expect(screen.getByText(/no priority segment could be chosen/i)).toBeInTheDocument();
    expect(screen.queryByText('Priority segment')).not.toBeInTheDocument();
  });

  it('explains a market stage that did not finish, with its reason', () => {
    const result = {
      ...RESULT,
      status: 'partial',
      market: null,
      errors: [{ stage: 'market_opportunity', code: 'llm_api_error', message: 'The AI service is busy right now.' }],
    } as typeof RESULT;
    renderTab(result);

    const alert = screen.getByRole('status');
    expect(alert).toHaveTextContent('Analysing the market did not finish');
    expect(alert).toHaveTextContent('The AI service is busy right now.');
  });

  it('explains a skipped market stage', () => {
    const result = {
      ...RESULT,
      status: 'partial',
      market: null,
      errors: [],
      notices: [
        {
          stage: 'market_opportunity',
          code: 'stage_skipped',
          severity: 'warning',
          message: 'Analysing the market was skipped because the web search did not finish.',
          detail: null,
        },
      ],
    } as typeof RESULT;
    renderTab(result);

    expect(screen.getByRole('status')).toHaveTextContent('skipped because the web search did not finish');
  });
});

describe('Market tab: in the run page', () => {
  it('opens from the tab bar and opens the source drawer on a citation', async () => {
    server.use(http.get(`${API_URL}/api/runs/live-agritech`, () => HttpResponse.json(LIVE)));
    const user = userEvent.setup();
    renderWithApp(
      <Routes>
        <Route path="/runs/:runId" element={<RunPage />} />
      </Routes>,
      { route: '/runs/live-agritech' },
    );

    await user.click(await screen.findByRole('tab', { name: 'Market' }));
    const panel = screen.getByRole('tabpanel');
    const size = within(panel).getByRole('region', { name: /market size/i });
    await user.click(within(size).getAllByRole('button', { name: /open the source details/i })[0]!);

    const drawer = await screen.findByRole('dialog');
    expect(within(drawer).getByRole('link', { name: /open source/i })).toHaveAttribute(
      'href',
      MARKET.sources!.find((source) => source.id === 'S1')!.url,
    );
  });
});

describe('evidence ids in free text', () => {
  it('splits around the ids and keeps every other word', () => {
    expect(splitEvidenceIds('between sources S2 and S3 regarding')).toEqual([
      'between sources ',
      { id: 'S2' },
      ' and ',
      { id: 'S3' },
      ' regarding',
    ]);
  });

  it('leaves text without ids alone, and does not take a word that only starts with S', () => {
    expect(splitEvidenceIds('Smallholder farmers in S-tier markets')).toEqual(['Smallholder farmers in S-tier markets']);
  });
});
