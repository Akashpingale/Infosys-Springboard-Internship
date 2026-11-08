/**
 * Sources tab (KIRO_UI_UPGRADE_SPEC.md Sections 7.4, 6.8 and 8.6).
 *
 * One row per page the evidence came from: its display number, title, domain, which analysis cited
 * it, the search engine's relevance score and how many findings rest on it. The table can be
 * searched and sorted, and opening a row shows the drawer with every finding that cites it.
 *
 * Two things are deliberate. The first column shows the small number the citation chips use, not
 * the backend's evidence id, because "S10" means nothing to a reader (Section 8.6) and the two
 * analyses number their evidence separately. And a score the search engine did not report is shown
 * as a dash with an explanation, never as a zero (Section 6.8).
 */

import { ArrowDown, ArrowUp, ArrowUpDown, Search } from 'lucide-react';
import * as React from 'react';

import { EmptyState } from '@/components/EmptyState';
import { controlClassName } from '@/components/Field';
import { Label } from '@/components/ui/label';
import { cn } from '@/lib/cn';
import { count } from '@/lib/format';
import {
  FIRST_DIRECTION,
  filterSourceRows,
  searchFacts,
  sortSourceRows,
  sourceRows,
  type SortColumn,
  type SortDirection,
  type SourceRow,
} from '@/lib/runDetails';
import type { Claim, PipelineResult, SourceRecord } from '@/lib/results';
import { NARROW, useMediaQuery } from '@/lib/useMediaQuery';

const COLUMNS: { key: SortColumn; label: string; align: 'left' | 'right'; hint?: string }[] = [
  { key: 'number', label: 'Source', align: 'left' },
  { key: 'title', label: 'Title', align: 'left' },
  { key: 'domain', label: 'Domain', align: 'left' },
  { key: 'section', label: 'Section', align: 'left' },
  { key: 'score', label: 'Score', align: 'right' },
  { key: 'citedBy', label: 'Cited by', align: 'right' },
];

export const SCORE_NOTE =
  'Score is the search engine\u2019s own relevance score for the query it answered, not a judgement ' +
  'of quality. A dash means it reported none.';

const SORT_ICON: Record<SortDirection, typeof ArrowUp> = { ascending: ArrowUp, descending: ArrowDown };

export interface SourcesTabProps {
  result: PipelineResult;
  sources: Map<string, SourceRecord>;
  claims: Claim[];
  onOpenSource: (key: string) => void;
}

export function SourcesTab({ result, sources, claims, onOpenSource }: SourcesTabProps) {
  const headingId = React.useId();
  const searchId = React.useId();
  const narrow = useMediaQuery(NARROW);
  const [term, setTerm] = React.useState('');
  const [sort, setSort] = React.useState<{ column: SortColumn; direction: SortDirection }>({
    column: 'number',
    direction: 'ascending',
  });

  const rows = React.useMemo(() => sourceRows(sources, claims, searchFacts(result)), [sources, claims, result]);
  const shown = React.useMemo(
    () => sortSourceRows(filterSourceRows(rows, term), sort.column, sort.direction),
    [rows, term, sort],
  );

  if (rows.length === 0) {
    return (
      <section aria-labelledby={headingId} className="space-y-4">
        <h2 id={headingId}>Sources</h2>
        <EmptyState message="This run cites no sources. Nothing in it rests on a page we can link to." />
      </section>
    );
  }

  function toggle(column: SortColumn): void {
    setSort((current) =>
      current.column === column
        ? { column, direction: current.direction === 'ascending' ? 'descending' : 'ascending' }
        : { column, direction: FIRST_DIRECTION[column] },
    );
  }

  return (
    <section aria-labelledby={headingId} className="space-y-6">
      <div className="space-y-2">
        <h2 id={headingId}>Sources</h2>
        <p className="max-w-prose text-body text-content-secondary">
          Every page the evidence came from. The number is the one on the citation chips, and the
          market and competitor analyses number their own evidence separately.
        </p>
      </div>

      <div className="flex flex-wrap items-end justify-between gap-4">
        <div data-print-hide className="w-full space-y-2 sm:w-80">
          <Label htmlFor={searchId}>Search the sources</Label>
          <div className="relative">
            <Search
              className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-content-muted"
              aria-hidden="true"
            />
            <input
              id={searchId}
              type="search"
              value={term}
              onChange={(event) => setTerm(event.target.value)}
              placeholder="Title, domain or search"
              className={cn(controlClassName, 'min-h-[44px] pl-9 sm:min-h-0')}
            />
          </div>
        </div>
        <p role="status" className="text-small text-content-muted">
          {term.trim()
            ? `Showing ${shown.length} of ${count(rows.length, 'source')}.`
            : `${count(rows.length, 'source')} in this result.`}
        </p>
      </div>

      {shown.length === 0 ? (
        <EmptyState message={`No source matches \u201c${term.trim()}\u201d. Clear the search to see them all.`} />
      ) : narrow ? (
        <>
          {/* A table of six columns cannot be read at 390 px, so the same rows become cards and
              the column headers become a row of sort buttons. */}
          <div role="group" aria-label="Sort the sources" data-print-hide className="flex flex-wrap gap-2">
            {COLUMNS.map((column) => {
              const active = sort.column === column.key;
              const Icon = active ? SORT_ICON[sort.direction] : ArrowUpDown;
              return (
                <button
                  key={column.key}
                  type="button"
                  aria-pressed={active}
                  onClick={() => toggle(column.key)}
                  className={cn(
                    'inline-flex min-h-[44px] items-center gap-2 rounded-pill border px-3 text-small',
                    active
                      ? 'border-line-strong bg-raised text-content'
                      : 'border-line bg-surface text-content-secondary',
                  )}
                >
                  {column.label}
                  <Icon className="size-3.5 shrink-0" aria-hidden="true" />
                </button>
              );
            })}
          </div>

          <ul className="space-y-3">
            {shown.map((row) => (
              <li key={row.source.key}>
                <Card row={row} onOpen={onOpenSource} />
              </li>
            ))}
          </ul>
        </>
      ) : (
        <div className="overflow-x-auto rounded-panel border border-line bg-surface">
          <table className="w-full min-w-[46rem] text-small">
            <caption className="sr-only">
              Sources in this result, sortable. {SCORE_NOTE}
            </caption>
            <thead>
              <tr className="border-b border-line">
                {COLUMNS.map((column) => {
                  const active = sort.column === column.key;
                  const Icon = active ? SORT_ICON[sort.direction] : ArrowUpDown;
                  return (
                    <th
                      key={column.key}
                      scope="col"
                      aria-sort={active ? sort.direction : 'none'}
                      className={cn('p-0 font-medium', column.align === 'right' ? 'text-right' : 'text-left')}
                    >
                      <button
                        type="button"
                        onClick={() => toggle(column.key)}
                        className={cn(
                          'flex w-full items-center gap-2 px-4 py-3 text-small font-medium',
                          'text-content-secondary transition-colors duration-tab hover:text-content',
                          column.align === 'right' && 'justify-end',
                        )}
                      >
                        {column.label}
                        <Icon className={cn('size-3.5 shrink-0', active ? 'text-content' : 'text-content-muted')} aria-hidden="true" />
                      </button>
                    </th>
                  );
                })}
              </tr>
            </thead>
            <tbody>
              {shown.map((row) => (
                <Row key={row.source.key} row={row} onOpen={onOpenSource} />
              ))}
            </tbody>
          </table>
        </div>
      )}

      <p className="max-w-prose text-small text-content-muted">{SCORE_NOTE}</p>
    </section>
  );
}

/** The score, or a dash with the reason said in words (Section 6.8). */
function Score({ score }: { score: number | null }) {
  if (score === null) {
    return (
      <>
        <span aria-hidden="true">{'\u2014'}</span>
        <span className="sr-only">No score reported</span>
      </>
    );
  }
  return <>{score.toFixed(2)}</>;
}

/** What a source came from, under its title: the search, or that it is the summary. */
function Provenance({ row }: { row: SourceRow }) {
  if (row.source.isSummary) {
    return (
      <p className="mt-1 text-micro text-content-muted">
        The search engine&rsquo;s own summary, not a page.
      </p>
    );
  }
  return row.foundIn ? (
    <p className="mt-1 text-micro text-content-muted">Found in the {row.foundIn} search</p>
  ) : null;
}

/**
 * One source as a card, for a narrow screen. It carries the same six values as a table row; the
 * column headers become the labels of a definition list, which is how a stacked table stays
 * readable to a screen reader.
 */
function Card({ row, onOpen }: { row: SourceRow; onOpen: (key: string) => void }) {
  const { source } = row;
  return (
    <div className="space-y-3 rounded-panel border border-line bg-surface p-4">
      <div className="flex items-start gap-3">
        <span className="tabular shrink-0 text-small text-content-muted">
          {source.isSummary ? (
            <>
              <span aria-hidden="true">{'\u2014'}</span>
              <span className="sr-only">No number: the search summary is shown as a labelled chip.</span>
            </>
          ) : (
            source.number
          )}
        </span>
        <div className="min-w-0 flex-1">
          <button
            type="button"
            onClick={() => onOpen(source.key)}
            className="min-h-[44px] text-left text-small text-content underline-offset-2 hover:underline"
          >
            {source.title}
          </button>
          <Provenance row={row} />
        </div>
      </div>

      <dl className="grid grid-cols-2 gap-x-4 gap-y-2 border-t border-line pt-3 text-micro">
        <div className="col-span-2 min-w-0">
          <dt className="text-content-muted">Domain</dt>
          <dd className="break-words font-mono text-content-secondary">{source.domain || '\u2014'}</dd>
        </div>
        <div>
          <dt className="text-content-muted">Section</dt>
          <dd className="text-content-secondary">{row.section}</dd>
        </div>
        <div>
          <dt className="text-content-muted">Score</dt>
          <dd className="tabular text-content-secondary">
            <Score score={row.score} />
          </dd>
        </div>
        <div>
          <dt className="text-content-muted">Cited by</dt>
          <dd className="tabular text-content">
            {row.citedBy === 0 ? (
              <>
                <span aria-hidden="true">0</span>
                <span className="sr-only">Cited by nothing in this result</span>
              </>
            ) : (
              row.citedBy
            )}
          </dd>
        </div>
      </dl>
    </div>
  );
}

function Row({ row, onOpen }: { row: SourceRow; onOpen: (key: string) => void }) {
  const { source } = row;
  return (
    <tr
      // Section 7.4: a row click opens the drawer. The title is a real button, so the keyboard can
      // reach it too and the row is not an invisible control.
      onClick={() => onOpen(source.key)}
      className="cursor-pointer border-b border-line last:border-0 hover:bg-raised"
    >
      <td className="tabular px-4 py-3 align-top text-content">
        {source.isSummary ? (
          <>
            <span aria-hidden="true">{'\u2014'}</span>
            <span className="sr-only">No number: the search summary is shown as a labelled chip.</span>
          </>
        ) : (
          source.number
        )}
      </td>
      <td className="max-w-[22rem] px-4 py-3 align-top">
        <button
          type="button"
          onClick={(event) => {
            event.stopPropagation();
            onOpen(source.key);
          }}
          className="text-left text-small text-content underline-offset-2 hover:underline"
        >
          {source.title}
        </button>
        <Provenance row={row} />
      </td>
      <td className="px-4 py-3 align-top font-mono text-micro text-content-secondary">
        {source.domain || '\u2014'}
      </td>
      <td className="px-4 py-3 align-top text-content-secondary">{row.section}</td>
      <td className="tabular px-4 py-3 text-right align-top text-content-secondary">
        <Score score={row.score} />
      </td>
      <td className="tabular px-4 py-3 text-right align-top text-content">
        {row.citedBy === 0 ? (
          <>
            <span aria-hidden="true">0</span>
            <span className="sr-only">Cited by nothing in this result</span>
          </>
        ) : (
          row.citedBy
        )}
      </td>
    </tr>
  );
}
