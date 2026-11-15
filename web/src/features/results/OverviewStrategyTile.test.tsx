import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { OverviewTab, strategyTile } from '@/features/results/OverviewTab';
import { buildSourceIndex, collectClaims, sourceKey, type PipelineResult } from '@/lib/results';
import { COMPLETE_RESULT } from '@/test/runFixtures';
import { SYNTHETIC_STRATEGY_RESULT } from '@/test/strategyHandlers';

const RESULT = SYNTHETIC_STRATEGY_RESULT;

function show(result: PipelineResult) {
  const opened = vi.fn();
  render(
    <OverviewTab
      result={result}
      sources={buildSourceIndex(result)}
      claims={collectClaims(result)}
      onOpenSource={opened}
    />,
  );
  return opened;
}

function tile(): HTMLElement {
  return screen.getByRole('heading', { level: 3, name: 'Strategy' }).parentElement!.parentElement!;
}

function summaryLine(start: string): HTMLElement {
  const summary = screen.getByRole('region', { name: 'Summary' });
  return within(summary)
    .getAllByRole('listitem')
    .find((item) => item.textContent?.startsWith(start))!;
}

describe('Overview: Strategy tile', () => {
  it('counts the risks and the first-release features when all three parts were generated', () => {
    show(RESULT);

    const strategy = tile();
    expect(strategy).toHaveTextContent('6 risks, 6 features for the first release');
    const chip = within(strategy).getByText('Generated');
    expect(chip.querySelector('svg')).toHaveAttribute('aria-hidden', 'true');
    expect(strategy).toHaveTextContent('SWOT and risk review, MVP plan and go-to-market plan.');
  });

  it('says partly generated and names the part that is missing', () => {
    show({ ...RESULT, gtm: null });

    const strategy = tile();
    expect(strategy).toHaveTextContent('6 risks, 6 features for the first release');
    expect(within(strategy).getByText('Partly generated').querySelector('svg')).not.toBeNull();
    expect(strategy).toHaveTextContent('Not generated: the go-to-market plan.');
  });

  it('counts only what is there when the SWOT is missing', () => {
    show({ ...RESULT, swot: null, gtm: null });

    const strategy = tile();
    expect(within(strategy).getByText('6 features for the first release')).toBeInTheDocument();
    expect(strategy).not.toHaveTextContent('risks,');
    expect(strategy).toHaveTextContent('Not generated: the SWOT and risk review and the go-to-market plan.');
  });

  it('says not generated for a result without any strategy', () => {
    show(COMPLETE_RESULT);

    const strategy = tile();
    expect(within(strategy).getByText('No strategy yet')).toBeInTheDocument();
    expect(within(strategy).getByText('Not generated').querySelector('svg')).not.toBeNull();
    expect(strategy).toHaveTextContent('There is no SWOT, MVP plan or go-to-market plan yet.');
  });

  it('works the states out from the result alone', () => {
    expect(strategyTile(RESULT)).toEqual({
      state: 'generated',
      value: '6 risks, 6 features for the first release',
      detail: 'SWOT and risk review, MVP plan and go-to-market plan.',
    });
    expect(strategyTile({ ...RESULT, swot: null, mvp: null }).value).toBe('Go-to-market plan');
    expect(strategyTile({ ...RESULT, swot: null, mvp: null }).state).toBe('partly');
    const oneRisk = { ...RESULT.swot!, risks: RESULT.swot!.risks!.slice(0, 1) };
    const oneFeature = { ...RESULT.mvp!, features: RESULT.mvp!.features!.slice(0, 1) };
    expect(strategyTile({ ...RESULT, swot: oneRisk, mvp: oneFeature }).value).toBe(
      '1 risk, 1 feature for the first release',
    );
    expect(strategyTile(COMPLETE_RESULT)).toEqual({
      state: 'none',
      value: null,
      detail: 'There is no SWOT, MVP plan or go-to-market plan yet.',
    });
  });

  it('adds one tile to the row and leaves the others as they were', () => {
    show(RESULT);

    const row = tile().parentElement!;
    expect(within(row).getAllByRole('heading', { level: 3 }).map((heading) => heading.textContent)).toEqual([
      'Evidence strength',
      'Market size (TAM)',
      'Competitors found',
      'Priority segment',
      'Strategy',
    ]);
  });
});

describe('Overview: strategy lines in the summary', () => {
  it('shows the main risk, the first-release scope and the start channel, each with its chips', async () => {
    const user = userEvent.setup();
    const opened = show(RESULT);

    const risk = summaryLine('Main risk (high severity, market): Farmers stay with the free app.');
    expect(within(risk).getAllByRole('button').map((chip) => chip.getAttribute('aria-label'))).toEqual([
      'Source 5: Plantix crop doctor app. Open the source details.',
      'Source 9: Plantix pricing. Open the source details.',
    ]);

    const scope = summaryLine('First release, the top 3 of 6 features:');
    expect(within(scope).getByText('From your idea')).toBeInTheDocument();
    expect(within(scope).queryByRole('button')).not.toBeInTheDocument();

    const start = summaryLine('Go-to-market, start here: Short demo videos on a messaging app.');
    await user.click(within(start).getByRole('button', { name: /^Source 2: Plantix crop doctor app/ }));
    expect(opened).toHaveBeenCalledWith(sourceKey('market', 'S2'));
  });

  it('adds no strategy line when the result has no strategy', () => {
    show(COMPLETE_RESULT);

    const summary = screen.getByRole('region', { name: 'Summary' });
    expect(summary).not.toHaveTextContent('Main risk');
    expect(summary).not.toHaveTextContent('First release');
    expect(summary).not.toHaveTextContent('start here');
  });
});
