/**
 * Reading a run's own record (KIRO_UI_UPGRADE_SPEC.md Sections 7.4 and 9).
 *
 * The Sources tab and the Run details tab both describe the run rather than the idea: which pages
 * the evidence came from, which searches were made, how long each stage took and what the quality
 * checks changed.
 *
 * As everywhere else, nothing is computed that the backend already states. A relevance score and a
 * snippet belong to the search engine's own result, so they are looked up by URL in the search
 * bundles the run returned; a source that is not in any of them has no score, and is shown as
 * having none rather than being given a zero.
 */

import type { components } from '@/api/types.gen';
import type { RunDetail, RunStage } from '@/features/run/useRun';
import type { AnalysisKey, Claim, Notice, PipelineResult, SourceRecord } from '@/lib/results';
import { claimsCiting } from '@/lib/results';

type SearchBundle = components['schemas']['SearchBundle'];

/** What the search engine recorded about one page, for the Sources table. */
export interface SearchFacts {
  /** The engine's own relevance score, 0 to 1. Null when it reported none. */
  score: number | null;
  snippet: string | null;
  /** The labelled search it came back from, such as "Market size and trends". */
  foundIn: string | null;
}

/** The analysis a source belongs to, in words, for the Section column. */
export const ANALYSIS_LABEL: Record<AnalysisKey, string> = {
  market: 'Market',
  competitors: 'Competitors',
};

/** Where each search bundle in a result came from, in the order the pipeline runs them. */
const BUNDLES: [keyof PipelineResult, string][] = [
  ['search', 'Searching the web'],
  ['market_search', 'Analysing the market'],
  ['competitor_search', 'Comparing competitors'],
];

function bundlesOf(result: PipelineResult): [string, SearchBundle][] {
  const found: [string, SearchBundle][] = [];
  for (const [field, stage] of BUNDLES) {
    const bundle = result[field] as SearchBundle | null | undefined;
    if (bundle && (bundle.sections ?? []).length > 0) {
      found.push([stage, bundle]);
    }
  }
  return found;
}

/**
 * What the search engine said about each page, keyed by URL.
 *
 * A page can come back from more than one search; the first is kept, so the label names where it
 * was first seen and the table does not change under the reader.
 */
export function searchFacts(result: PipelineResult): Map<string, SearchFacts> {
  const facts = new Map<string, SearchFacts>();
  for (const [, bundle] of bundlesOf(result)) {
    for (const section of bundle.sections ?? []) {
      for (const entry of section.results ?? []) {
        if (!entry.url || facts.has(entry.url)) {
          continue;
        }
        facts.set(entry.url, {
          score: typeof entry.score === 'number' ? entry.score : null,
          snippet: entry.snippet?.trim() ? entry.snippet : null,
          foundIn: section.label || null,
        });
      }
    }
  }
  return facts;
}

export interface SourceRow {
  source: SourceRecord;
  /** "Market" or "Competitors": which analysis numbered and cited it. */
  section: string;
  score: number | null;
  snippet: string | null;
  foundIn: string | null;
  /** How many findings in the result rest on it. */
  citedBy: number;
}

/** One row per source, with the search facts and the citation count attached. */
export function sourceRows(
  sources: Map<string, SourceRecord>,
  claims: Claim[],
  facts: Map<string, SearchFacts>,
): SourceRow[] {
  return [...sources.values()].map((source) => {
    const found = source.url ? facts.get(source.url) : undefined;
    return {
      source,
      section: ANALYSIS_LABEL[source.analysis],
      score: found?.score ?? null,
      snippet: found?.snippet ?? null,
      foundIn: found?.foundIn ?? null,
      citedBy: claimsCiting(claims, source.key).length,
    };
  });
}

export type SortColumn = 'number' | 'title' | 'domain' | 'section' | 'score' | 'citedBy';
export type SortDirection = 'ascending' | 'descending';

/** Which way a column reads first: text from A, numbers from the largest, which is what is wanted. */
export const FIRST_DIRECTION: Record<SortColumn, SortDirection> = {
  number: 'ascending',
  title: 'ascending',
  domain: 'ascending',
  section: 'ascending',
  score: 'descending',
  citedBy: 'descending',
};

/** Numbers compare as numbers, text as text, and a missing value always sorts last. */
function compare(a: SourceRow, b: SourceRow, column: SortColumn): number {
  switch (column) {
    case 'number':
      return a.source.number - b.source.number;
    case 'title':
      return a.source.title.localeCompare(b.source.title);
    case 'domain':
      return a.source.domain.localeCompare(b.source.domain);
    case 'section':
      return a.section.localeCompare(b.section);
    case 'citedBy':
      return a.citedBy - b.citedBy;
    case 'score':
      return (a.score ?? -1) - (b.score ?? -1);
  }
}

/**
 * The rows in order. Ties keep their display number, so the order is the same on every render, and
 * a source with no score stays at the bottom whichever way the column is sorted.
 */
export function sortSourceRows(rows: SourceRow[], column: SortColumn, direction: SortDirection): SourceRow[] {
  const sign = direction === 'ascending' ? 1 : -1;
  return [...rows].sort((a, b) => {
    if (column === 'score') {
      const missing = Number(a.score === null) - Number(b.score === null);
      if (missing !== 0) {
        return missing;
      }
    }
    return compare(a, b, column) * sign || a.source.number - b.source.number;
  });
}

/** The rows whose title, domain or search matches what was typed. Matching ignores case. */
export function filterSourceRows(rows: SourceRow[], term: string): SourceRow[] {
  const needle = term.trim().toLowerCase();
  if (!needle) {
    return rows;
  }
  return rows.filter((row) =>
    [row.source.title, row.source.domain, row.section, row.foundIn ?? '']
      .join(' ')
      .toLowerCase()
      .includes(needle),
  );
}

export interface QueryRow {
  /** The labelled search, such as "Competitors". Null for a query recorded without one. */
  label: string | null;
  query: string;
  /** How many results came back, or null when the run did not record them. */
  results: number | null;
  error: string | null;
}

export interface QueryGroup {
  /** The stage that made these searches, in the stage's own words. */
  stage: string;
  rows: QueryRow[];
}

/**
 * Every search the run made, grouped by the stage that made it.
 *
 * The competitor analysis also records the queries it used as plain strings. Those that a search
 * bundle already lists are left out, so no query is shown twice.
 */
export function queryGroups(result: PipelineResult): QueryGroup[] {
  const groups: QueryGroup[] = [];
  const seen = new Set<string>();

  for (const [stage, bundle] of bundlesOf(result)) {
    const rows: QueryRow[] = [];
    for (const section of bundle.sections ?? []) {
      seen.add(section.query.trim());
      rows.push({
        label: section.label || null,
        query: section.query,
        results: (section.results ?? []).length,
        error: section.error ?? null,
      });
    }
    groups.push({ stage, rows });
  }

  const extra = (result.competitors?.queries_used ?? [])
    .filter((query) => !seen.has(query.trim()))
    .map((query) => ({ label: null, query, results: null, error: null }));
  if (extra.length > 0) {
    const existing = groups.find((group) => group.stage === 'Comparing competitors');
    if (existing) {
      existing.rows.push(...extra);
    } else {
      groups.push({ stage: 'Comparing competitors', rows: extra });
    }
  }

  return groups;
}

export interface StageBar {
  key: string;
  label: string;
  status: RunStage['status'];
  /** Seconds, or null when the stage did not run. */
  seconds: number | null;
}

export interface StageTiming {
  bars: StageBar[];
  /** The backend's own total when it reported one, otherwise the stages added up. */
  total: number;
  /** True when the total came from the result rather than from adding the stages. */
  totalFromResult: boolean;
}

/**
 * How long each stage took (Section 9, chart 3).
 *
 * The durations are the run's own stage records. The total prefers `timings.total`, which the
 * pipeline measured end to end and which therefore includes the time between stages.
 */
export function stageTiming(run: RunDetail): StageTiming {
  const bars: StageBar[] = run.stages.map((stage) => ({
    key: stage.key,
    label: stage.label,
    status: stage.status,
    seconds: typeof stage.duration_s === 'number' ? stage.duration_s : null,
  }));
  const added = bars.reduce((sum, bar) => sum + (bar.seconds ?? 0), 0);
  const reported = run.result?.timings?.['total'];
  const hasReported = typeof reported === 'number' && reported > 0;
  return {
    bars,
    total: hasReported ? reported : added,
    totalFromResult: hasReported,
  };
}

export interface NoticeGroup {
  /** The stage's own label, or "Other" for a notice that names no stage. */
  stage: string;
  notices: Notice[];
}

export const UNGROUPED_STAGE = 'Other notes';

/**
 * Notices grouped by the stage that raised them, in the order the stages run, so the panel reads
 * in the same order as the stage tracker.
 */
export function noticeGroups(notices: Notice[], stages: RunStage[]): NoticeGroup[] {
  const groups: NoticeGroup[] = [];
  for (const stage of stages) {
    const mine = notices.filter((notice) => notice.stage === stage.key);
    if (mine.length > 0) {
      groups.push({ stage: stage.label, notices: mine });
    }
  }
  const known = new Set(stages.map((stage) => stage.key));
  const rest = notices.filter((notice) => !notice.stage || !known.has(notice.stage));
  if (rest.length > 0) {
    groups.push({ stage: UNGROUPED_STAGE, notices: rest });
  }
  return groups;
}

/** A file name for a download: the run's title, lower case, with a date. Never a path. */
export function downloadName(run: RunDetail, extension: string): string {
  const slug = run.title
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 60);
  const day = (run.created_at ?? '').slice(0, 10) || 'run';
  return `validation-${slug || 'result'}-${day}.${extension}`;
}
