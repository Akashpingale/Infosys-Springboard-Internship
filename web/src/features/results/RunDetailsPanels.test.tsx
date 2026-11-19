import { render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { RunDetailsTab } from '@/features/results/RunDetailsTab';
import { USAGE_NOT_RECORDED, UsageTable, usageRows } from '@/features/results/UsageTable';
import { VERSIONS_NOT_RECORDED, VersionsPanel } from '@/features/results/VersionsPanel';
import type { PipelineResult } from '@/lib/results';
import { renderWithApp } from '@/test/render';
import { DONE } from '@/test/runFixtures';

const USAGE: NonNullable<PipelineResult['usage']> = {
  llm_calls: 7,
  search_calls: 12,
  by_stage: {
    competitor_analysis: { llm_calls: 3, search_calls: 7, seconds: 56.9 },
    extraction: { llm_calls: 1, search_calls: 0, seconds: 6.5 },
    search: { llm_calls: 0, search_calls: 4, seconds: 18.2 },
    market_opportunity: { llm_calls: 3, search_calls: 1, seconds: 27.3 },
  },
};
const VERSIONS: NonNullable<PipelineResult['versions']> = {
  query_profile: 'v1',
  prompt_profile: 'v1',
  prompt_versions: { extraction: 'extraction-v1', market: 'market-v1', competitors: 'competitors-v1', future: 'future-v9' },
  app_version: '0.1.0',
};

describe('Run details: usage', () => {
  it('lists AI requests and searches per stage in the order the stages ran, with the totals', () => {
    render(<UsageTable usage={USAGE} stages={DONE.stages} />);

    const table = screen.getByRole('table');
    const rows = within(table)
      .getAllByRole('row')
      .slice(1)
      .map((row) => Array.from(row.querySelectorAll('th, td')).map((cell) => cell.textContent));
    expect(rows).toEqual([
      ['Understanding your idea', '1', '0'],
      ['Searching the web', '0', '4'],
      ['Analysing the market', '3', '1'],
      ['Comparing competitors', '3', '7'],
      ['Total', '7', '12'],
    ]);
    expect(within(table).getAllByRole('columnheader').map((cell) => cell.textContent)).toEqual([
      'Stage',
      'AI requests',
      'Searches',
    ]);
  });

  it('keeps a stage the run list does not name, under its own key', () => {
    const rows = usageRows({ ...USAGE, by_stage: { ...USAGE.by_stage, report: { llm_calls: 1, search_calls: 0, seconds: 2 } } }, DONE.stages);

    expect(rows.at(-1)).toEqual({ key: 'report', label: 'report', llm: 1, search: 0 });
  });

  it('says when a run recorded no usage, rather than showing zeros', () => {
    render(<UsageTable usage={null} stages={DONE.stages} />);

    expect(screen.getByText(USAGE_NOT_RECORDED)).toBeInTheDocument();
    expect(screen.queryByRole('table')).not.toBeInTheDocument();
  });
});

describe('Run details: versions', () => {
  it('shows the profiles, the app version and each prompt version', () => {
    render(<VersionsPanel versions={VERSIONS} />);

    const terms = screen.getAllByRole('term').map((term) => term.textContent);
    const values = screen.getAllByRole('definition').map((value) => value.textContent);
    expect(terms).toEqual([
      'Query profile',
      'Prompt profile',
      'App version',
      'Prompt: Understanding your idea',
      'Prompt: Market analysis',
      'Prompt: Competitor analysis',
      'Prompt: future',
    ]);
    expect(values).toEqual(['v1', 'v1', '0.1.0', 'extraction-v1', 'market-v1', 'competitors-v1', 'future-v9']);
  });

  it('says when a run recorded no versions', () => {
    render(<VersionsPanel versions={undefined} />);

    expect(screen.getByText(VERSIONS_NOT_RECORDED)).toBeInTheDocument();
  });

  it('appear in the Run details tab, after the stage timings', () => {
    const result = { ...DONE.result!, usage: USAGE, versions: VERSIONS };
    renderWithApp(<RunDetailsTab run={DONE} result={result} />);

    const usage = screen.getByRole('region', { name: 'Usage' });
    const versions = screen.getByRole('region', { name: 'Versions' });
    expect(within(usage).getByRole('table')).toBeInTheDocument();
    expect(within(versions).getByText('market-v1')).toBeInTheDocument();
    expect(usage.compareDocumentPosition(versions) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it('show the not-recorded lines for a result saved before Milestone 4', () => {
    renderWithApp(<RunDetailsTab run={DONE} result={DONE.result!} />);

    expect(screen.getByText(USAGE_NOT_RECORDED)).toBeInTheDocument();
    expect(screen.getByText(VERSIONS_NOT_RECORDED)).toBeInTheDocument();
  });
});
