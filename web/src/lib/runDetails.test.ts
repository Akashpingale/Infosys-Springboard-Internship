/**
 * The run-record helpers (KIRO_UI_UPGRADE_SPEC.md Sections 7.4 and 9).
 *
 * The fixture is the saved live fintech run, read as test data, so these check real pipeline output:
 * only 9 of its 21 sources carry a relevance score, which is exactly the case a table must handle
 * without inventing a number.
 */

import { describe, expect, it } from 'vitest';

import type { RunDetail } from '@/features/run/useRun';
import {
  downloadName,
  filterSourceRows,
  noticeGroups,
  queryGroups,
  searchFacts,
  sortSourceRows,
  sourceRows,
  stageTiming,
  type SourceRow,
} from '@/lib/runDetails';
import { buildSourceIndex, collectClaims, type PipelineResult } from '@/lib/results';
import fintech from '@/test/liveFintech.json';

const LIVE = fintech as unknown as RunDetail;
const RESULT = LIVE.result!;

function rows(result: PipelineResult = RESULT): SourceRow[] {
  return sourceRows(buildSourceIndex(result), collectClaims(result), searchFacts(result));
}

describe('searchFacts', () => {
  it('takes the score and the search label from the search results themselves', () => {
    const facts = searchFacts(RESULT);
    const first = facts.get('https://finance.yahoo.com/news/digital-banking-platform-market-size-140600294.html');

    expect(first?.score).toBeCloseTo(0.5544, 3);
    expect(first?.foundIn).toBe('Market size and trends');
    expect(first?.snippet).toBeTruthy();
  });

  it('leaves out a page no search returned, rather than giving it a zero', () => {
    const facts = searchFacts(RESULT);
    const scored = rows().filter((row) => row.score !== null);

    expect(facts.size).toBe(12);
    expect(scored).toHaveLength(9);
    expect(rows().filter((row) => row.score === null)).toHaveLength(12);
  });

  it('finds nothing when the run kept no search bundle', () => {
    expect(searchFacts({ ...RESULT, search: null } as PipelineResult).size).toBe(0);
  });
});

describe('sourceRows', () => {
  it('keeps one row per source, numbered across both analyses', () => {
    const all = rows();

    expect(all).toHaveLength(21);
    expect(all.map((row) => row.source.number)).toEqual(Array.from({ length: 21 }, (_, index) => index + 1));
    expect(all.filter((row) => row.section === 'Market')).toHaveLength(10);
    expect(all.filter((row) => row.section === 'Competitors')).toHaveLength(11);
  });

  it('counts the findings that rest on each source', () => {
    const khatabook = rows().find((row) => row.source.title.startsWith('Khatabook: Reviews'));

    expect(khatabook?.citedBy).toBeGreaterThan(0);
    expect(rows().every((row) => row.citedBy >= 0)).toBe(true);
  });

  it('keeps the same page separate when each analysis cited it', () => {
    const shared = rows().filter((row) => row.source.domain === 'systemsandteams.com');

    // The market analysis numbered it S4 and the competitor analysis S1: one page, two rows.
    expect(shared).toHaveLength(2);
    expect(shared.map((row) => row.section)).toEqual(['Market', 'Competitors']);
    expect(new Set(shared.map((row) => row.source.number)).size).toBe(2);
  });
});

describe('sortSourceRows', () => {
  it('sorts by number, title, domain and citation count both ways', () => {
    const all = rows();

    expect(sortSourceRows(all, 'number', 'ascending')[0]?.source.number).toBe(1);
    expect(sortSourceRows(all, 'number', 'descending')[0]?.source.number).toBe(21);

    const byTitle = sortSourceRows(all, 'title', 'ascending').map((row) => row.source.title);
    expect(byTitle).toEqual([...byTitle].sort((a, b) => a.localeCompare(b)));

    const byCited = sortSourceRows(all, 'citedBy', 'descending').map((row) => row.citedBy);
    expect(byCited[0]).toBe(Math.max(...all.map((row) => row.citedBy)));
  });

  it('puts a source with no score last, whichever way the column is sorted', () => {
    const all = rows();
    const down = sortSourceRows(all, 'score', 'descending');
    const up = sortSourceRows(all, 'score', 'ascending');

    expect(down[0]?.score).toBeCloseTo(0.7807, 3);
    expect(down.slice(-12).every((row) => row.score === null)).toBe(true);
    expect(up[0]?.score).toBeCloseTo(0.4364, 3);
    expect(up.slice(-12).every((row) => row.score === null)).toBe(true);
  });

  it('breaks a tie by the display number, so the order never shifts', () => {
    const all = rows();
    const first = sortSourceRows(all, 'section', 'ascending');
    const again = sortSourceRows([...all].reverse(), 'section', 'ascending');

    expect(first.map((row) => row.source.key)).toEqual(again.map((row) => row.source.key));
  });
});

describe('filterSourceRows', () => {
  it('matches the title, the domain, the section and the search, ignoring case', () => {
    const all = rows();

    expect(filterSourceRows(all, 'khatabook').length).toBeGreaterThan(0);
    expect(filterSourceRows(all, 'QUICKBOOKS.INTUIT.COM')).toHaveLength(1);
    // The section is searched as well, so every row of the market analysis matches "market".
    expect(filterSourceRows(all, 'market').length).toBeGreaterThanOrEqual(10);
    expect(filterSourceRows(all, 'recent news and funding').length).toBeGreaterThan(0);
  });

  it('returns everything for an empty search and nothing for a miss', () => {
    expect(filterSourceRows(rows(), '   ')).toHaveLength(21);
    expect(filterSourceRows(rows(), 'no such page')).toHaveLength(0);
  });
});

describe('queryGroups', () => {
  it('groups the searches by the stage that made them', () => {
    const groups = queryGroups(RESULT);

    expect(groups.map((group) => group.stage)).toEqual(['Searching the web', 'Comparing competitors']);
    expect(groups[0]?.rows).toHaveLength(4);
    expect(groups[0]?.rows[0]?.label).toBe('Market size and trends');
    expect(groups[0]?.rows[0]?.results).toBe(3);
  });

  it('adds the competitor queries and records that their result count is unknown', () => {
    const competitors = queryGroups(RESULT).find((group) => group.stage === 'Comparing competitors');

    expect(competitors?.rows).toHaveLength(5);
    expect(competitors?.rows.map((row) => row.query)).toContain('Khatabook pricing features');
    expect(competitors?.rows.every((row) => row.results === null)).toBe(true);
  });

  it('never lists the same query twice', () => {
    const shared = 'Finance / FinTech startups funding news recent';
    const result = {
      ...RESULT,
      competitors: { ...RESULT.competitors!, queries_used: [shared, 'something else'] },
    } as PipelineResult;

    const queries = queryGroups(result).flatMap((group) => group.rows.map((row) => row.query));
    expect(queries.filter((query) => query === shared)).toHaveLength(1);
    expect(queries).toContain('something else');
  });

  it('is empty when the run recorded no search at all', () => {
    const bare = { ...RESULT, search: null, competitors: null } as PipelineResult;
    expect(queryGroups(bare)).toEqual([]);
  });
});

describe('stageTiming', () => {
  it("prefers the pipeline's own total over adding the stages up", () => {
    const timing = stageTiming(LIVE);

    expect(timing.bars).toHaveLength(4);
    expect(timing.total).toBeCloseTo(102.486, 3);
    expect(timing.totalFromResult).toBe(true);
  });

  it('adds the stages up when the result reports no total', () => {
    const run = { ...LIVE, result: { ...RESULT, timings: {} } } as RunDetail;
    const timing = stageTiming(run);

    expect(timing.totalFromResult).toBe(false);
    expect(timing.total).toBeCloseTo(13.948 + 14.682 + 26.43 + 47.425, 3);
  });

  it('leaves a stage that never ran without a duration', () => {
    const run = {
      ...LIVE,
      stages: [{ key: 'search', label: 'Searching the web', status: 'skipped', duration_s: null }],
      result: { ...RESULT, timings: {} },
    } as unknown as RunDetail;

    expect(stageTiming(run).bars[0]?.seconds).toBeNull();
    expect(stageTiming(run).total).toBe(0);
  });
});

describe('noticeGroups', () => {
  it('groups the notices by stage, in the order the stages run', () => {
    const groups = noticeGroups(RESULT.notices ?? [], LIVE.stages);

    expect(groups).toHaveLength(2);
    expect(groups[0]?.notices).toHaveLength(2);
    expect(groups[1]?.notices).toHaveLength(1);
    expect(groups.map((group) => group.stage)).toEqual([
      LIVE.stages[2]?.label,
      LIVE.stages[3]?.label,
    ]);
  });

  it('keeps a notice that names no stage rather than dropping it', () => {
    const loose = { stage: null, code: 'odd', severity: 'info' as const, message: 'Something to note.' };
    const groups = noticeGroups([loose], LIVE.stages);

    expect(groups).toHaveLength(1);
    expect(groups[0]?.stage).toBe('Other notes');
  });
});

describe('downloadName', () => {
  it('builds a safe file name from the title and the date', () => {
    const name = downloadName(LIVE, 'md');

    expect(name.startsWith('validation-cash-flow-and-expense-management-platform')).toBe(true);
    expect(name.endsWith('-2026-10-27.md')).toBe(true);
    expect(name).toMatch(/^[a-z0-9.-]+$/);
  });

  it('keeps a long title short enough to be a file name', () => {
    const long = { ...LIVE, title: 'a'.repeat(300) } as RunDetail;
    // 60 characters of title, plus the fixed wrapper and the date.
    expect(downloadName(long, 'json')).toBe(`validation-${'a'.repeat(60)}-2026-10-27.json`);
  });

  it('never produces a path, and copes with a title of punctuation', () => {
    const odd = { ...LIVE, title: '../../etc/passwd ???' } as RunDetail;
    const name = downloadName(odd, 'json');

    expect(name).not.toContain('/');
    expect(name).not.toContain('..');
    expect(name).toBe('validation-etc-passwd-2026-10-27.json');
  });
});
