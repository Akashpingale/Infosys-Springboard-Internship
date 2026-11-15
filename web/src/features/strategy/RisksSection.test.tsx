import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { RisksSection } from '@/features/strategy/RisksSection';
import { buildSourceIndex, sourceKey } from '@/lib/results';
import { NARROW } from '@/lib/useMediaQuery';
import { SYNTHETIC_STRATEGY_RESULT } from '@/test/strategyHandlers';

const SWOT = SYNTHETIC_STRATEGY_RESULT.swot!;
const SOURCES = buildSourceIndex(SYNTHETIC_STRATEGY_RESULT);
const WIDE_MATCH_MEDIA = window.matchMedia;

const BY_SEVERITY = [
  'Farmers stay with the free app',
  'Wrong diagnosis on poor photos',
  'Cooperatives delay adoption',
  'Farmers resist paying',
  'Advice goes out of date',
  'Drone services win cooperatives',
];

function show(swot = SWOT) {
  const opened = vi.fn();
  render(<RisksSection swot={swot} sources={SOURCES} onOpenSource={opened} />);
  return opened;
}

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

function rowTitles(): string[] {
  return screen
    .getAllByRole('rowheader')
    .map((cell) => cell.firstElementChild?.textContent ?? '');
}

afterEach(() => {
  Object.defineProperty(window, 'matchMedia', { writable: true, configurable: true, value: WIDE_MATCH_MEDIA });
});

describe('Risks section: summary and coverage', () => {
  it('counts the risks by severity', () => {
    show();

    expect(screen.getByText('6 risks: 2 high, 2 medium, 2 low')).toBeInTheDocument();
  });

  it('shows one coverage chip per category, with its count', () => {
    show();

    const chips = within(screen.getByRole('list', { name: 'Risks by category' })).getAllByRole('listitem');
    expect(chips.map((chip) => chip.textContent)).toEqual([
      'Business: 1 risk',
      'Market: 2 risks',
      'Technical: 1 risk',
      'Financial: 1 risk',
      'Operational: 1 risk',
    ]);
    expect(screen.queryByText(/Not checked is not the same as safe/)).not.toBeInTheDocument();
  });

  it('says plainly when a category has no risk, and that this is not the same as safe', () => {
    show({
      ...SWOT,
      risks: (SWOT.risks ?? []).filter((risk) => risk.category !== 'financial' && risk.category !== 'operational'),
      risk_category_coverage: { business: 1, market: 2, technical: 1, financial: 0, operational: 0 },
      coverage_gaps: ['financial', 'operational'],
    });

    const chips = within(screen.getByRole('list', { name: 'Risks by category' })).getAllByRole('listitem');
    expect(chips[3]).toHaveTextContent('Financial: none found');
    expect(chips[4]).toHaveTextContent('Operational: none found');
    expect(
      screen.getByText('Financial and Operational: None found in this run. Not checked is not the same as safe.'),
    ).toBeInTheDocument();
    expect(screen.getByText('4 risks: 2 high, 1 medium, 1 low')).toBeInTheDocument();
  });
});

describe('Risks section: the register', () => {
  it('is a table on a wide screen with the planned columns, and no cards', () => {
    show();

    const table = screen.getByRole('table');
    expect(within(table).getAllByRole('columnheader').map((cell) => cell.textContent)).toEqual([
      'Risk',
      'Category',
      'Likelihood',
      'Impact',
      'Severity',
      'Mitigation',
    ]);
    expect(rowTitles()).toEqual(BY_SEVERITY);
    expect(screen.queryByRole('list', { name: 'Risk register' })).not.toBeInTheDocument();
    expect(screen.queryAllByRole('article')).toHaveLength(0);
  });

  it('shows severity as an icon and a word, never colour alone', () => {
    show();

    const rows = screen.getAllByRole('row').slice(1);
    const severities = rows.map((row) => within(row).getAllByRole('cell')[3]!);
    expect(severities.map((cell) => cell.textContent)).toEqual(['High', 'High', 'Medium', 'Medium', 'Low', 'Low']);
    for (const cell of severities) {
      const icon = cell.querySelector('svg');
      expect(icon).not.toBeNull();
      expect(icon).toHaveAttribute('aria-hidden', 'true');
    }
    const cells = within(rows[0]!).getAllByRole('cell').map((cell) => cell.textContent);
    expect(cells).toEqual([
      'Market',
      'High',
      'High',
      'High',
      'Run a small pilot that tests farmers stay with the free app.',
    ]);
  });

  it('becomes cards below 1024 px, with only one layout in the page', () => {
    narrow();
    show();

    expect(screen.queryByRole('table')).not.toBeInTheDocument();
    const cards = screen.getAllByRole('article');
    expect(cards).toHaveLength(6);
    expect(within(cards[0]!).getByRole('heading', { name: 'Farmers stay with the free app' })).toBeInTheDocument();
    expect(within(cards[0]!).getByText('High severity').querySelector('svg')).not.toBeNull();
    expect(cards[0]).toHaveTextContent('LikelihoodHigh');
    expect(cards[0]).toHaveTextContent('ImpactHigh');
    expect(screen.getAllByText('Farmers stay with the free app')).toHaveLength(1);
  });

  it('sorts by severity by default, and by category on request', async () => {
    const user = userEvent.setup();
    show();

    const select = screen.getByRole('combobox', { name: 'Sort risks by' });
    expect(select).toHaveValue('severity');

    await user.selectOptions(select, 'category');
    expect(rowTitles()).toEqual([
      'Cooperatives delay adoption',
      'Farmers stay with the free app',
      'Drone services win cooperatives',
      'Wrong diagnosis on poor photos',
      'Farmers resist paying',
      'Advice goes out of date',
    ]);

    await user.selectOptions(select, 'severity');
    expect(rowTitles()).toEqual(BY_SEVERITY);
  });

  it('opens the detail of a risk: description, early warning sign, confidence, basis and sources', async () => {
    const user = userEvent.setup();
    const opened = show();

    const toggle = screen.getByRole('button', { name: /^Show details\s*for Farmers stay with the free app$/ });
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
    expect(screen.queryByText('The incumbent already has wide reach.')).not.toBeInTheDocument();

    await user.click(toggle);

    expect(toggle).toHaveAttribute('aria-expanded', 'true');
    const detail = document.getElementById(toggle.getAttribute('aria-controls')!)!;
    expect(detail).toHaveTextContent('The incumbent already has wide reach.');
    expect(detail).toHaveTextContent(
      'Early warning signPilot users raise farmers stay with the free app in interviews.',
    );
    expect(detail).toHaveTextContent('ConfidenceLow');
    expect(within(detail).getByText('AI interpretation')).toBeInTheDocument();

    await user.click(within(detail).getByRole('button', { name: /^Source 5: Plantix crop doctor app/ }));
    expect(opened).toHaveBeenCalledWith(sourceKey('competitors', 'S1'));
  });

  it('opens the same detail from a card', async () => {
    narrow();
    const user = userEvent.setup();
    show();

    const card = screen.getAllByRole('article')[1]!;
    await user.click(within(card).getByRole('button', { name: /Show details/ }));
    expect(card).toHaveTextContent('Blurry images may mislead the model.');
    expect(card).toHaveTextContent('ConfidenceLow');
  });
});
