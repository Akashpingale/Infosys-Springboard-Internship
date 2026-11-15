import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { BASIS_LABELS } from '@/components/BasisChip';
import { SwotSection } from '@/features/strategy/SwotSection';
import { buildSourceIndex, sourceKey } from '@/lib/results';
import { SYNTHETIC_STRATEGY_RESULT } from '@/test/strategyHandlers';

const SWOT = SYNTHETIC_STRATEGY_RESULT.swot!;
const SOURCES = buildSourceIndex(SYNTHETIC_STRATEGY_RESULT);

function show(swot = SWOT) {
  const opened = vi.fn();
  render(<SwotSection swot={swot} sources={SOURCES} onOpenSource={opened} />);
  return opened;
}

function quadrant(name: string): HTMLElement {
  return screen.getByRole('region', { name });
}

describe('SWOT section', () => {
  it('shows the four quadrants in the planned order, each with its count', () => {
    show();

    const headings = screen.getAllByRole('heading', { level: 3 }).map((heading) => heading.textContent);
    expect(headings).toEqual(['Strengths', 'Weaknesses', 'Opportunities', 'Threats']);
    for (const name of ['Strengths', 'Weaknesses', 'Opportunities', 'Threats']) {
      expect(within(quadrant(name)).getByText('3 points')).toBeInTheDocument();
      expect(within(quadrant(name)).getAllByRole('listitem')).toHaveLength(3);
    }
  });

  it('keeps each point as the agent wrote it, with why it matters below', () => {
    show();

    const item = within(quadrant('Strengths')).getAllByRole('listitem')[0]!;
    expect(item).toHaveTextContent('The app diagnoses crop disease from a single phone photo.');
    expect(within(item).getByText('It shapes the first release.')).toHaveClass('text-content-muted');
  });

  it('gives every point exactly one basis chip, in words', () => {
    show();

    const claims = document.querySelectorAll('[data-claim]');
    expect(claims).toHaveLength(12);
    const words = Object.values(BASIS_LABELS);
    for (const claim of claims) {
      const found = words.filter((word) => within(claim as HTMLElement).queryAllByText(word).length > 0);
      expect(found).toHaveLength(1);
    }
    expect(within(quadrant('Strengths')).getAllByText('From your idea')).toHaveLength(3);
    expect(within(quadrant('Weaknesses')).getAllByText('Assumption')).toHaveLength(2);
  });

  it('numbers the citations and opens the source each one names, across both analyses', async () => {
    const user = userEvent.setup();
    const opened = show();

    const late = within(quadrant('Opportunities')).getAllByRole('listitem')[0]!;
    await user.click(within(late).getByRole('button', { name: /^Source 4: Farmer survey/ }));
    expect(opened).toHaveBeenLastCalledWith(sourceKey('market', 'S5'));

    const free = within(quadrant('Threats')).getAllByRole('listitem')[0]!;
    const chips = within(free).getAllByRole('button');
    expect(chips.map((chip) => chip.textContent)).toEqual(['5', '9', '2']);
    await user.click(chips[0]!);
    expect(opened).toHaveBeenLastCalledWith(sourceKey('competitors', 'S1'));
  });

  it('ends with the summary, labelled as an AI interpretation', () => {
    show();

    const summary = screen.getByText(SWOT.summary);
    expect(summary.parentElement).toHaveTextContent('AI interpretation');
  });

  it('says so when a quadrant has nothing', () => {
    show({ ...SWOT, threats: [] });

    expect(within(quadrant('Threats')).getByText('0 points')).toBeInTheDocument();
    expect(within(quadrant('Threats')).getByText('None found in this run.')).toBeInTheDocument();
  });
});
