import { AlertTriangle, CircleHelp, Info } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import * as React from 'react';

import { BasisChip, type Basis } from '@/components/BasisChip';
import type { components } from '@/api/types.gen';
import { REPORT_COPY } from '@/features/report/copy';
import type { ReportBlock } from '@/features/report/useReport';
import { cn } from '@/lib/cn';

type CalloutKind = components['schemas']['CalloutBlock']['kind'];
type TableBlock = components['schemas']['TableBlock'];

export const CALLOUT: Record<CalloutKind, { Icon: LucideIcon; word: string; box: string; icon: string }> = {
  note: { Icon: Info, word: 'Note', box: 'border-info-border bg-info-bg', icon: 'text-info' },
  caveat: { Icon: CircleHelp, word: 'Caveat', box: 'border-line-strong bg-raised', icon: 'text-content-muted' },
  warning: { Icon: AlertTriangle, word: 'Warning', box: 'border-warning-border bg-warning-bg', icon: 'text-warning' },
};

export const SOURCES_COLUMN = 'Sources';

export function sourceAnchor(number: number): string {
  return `report-source-${number}`;
}

export interface CitesProps {
  cites: number[] | undefined;
  onCite: (number: number) => void;
}

export function Cites({ cites, onCite }: CitesProps) {
  const numbers = [...new Set(cites ?? [])];
  if (numbers.length === 0) {
    return null;
  }
  return (
    <span className="inline-flex flex-wrap items-center gap-1 align-baseline">
      {numbers.map((number) => (
        <a
          key={number}
          href={`#${sourceAnchor(number)}`}
          onClick={(event) => {
            event.preventDefault();
            onCite(number);
          }}
          className="inline-flex min-h-6 items-center rounded-control px-1 text-small text-primary underline underline-offset-2 hover:text-primary-hover"
        >
          <span className="sr-only">Source </span>[{number}]
        </a>
      ))}
    </span>
  );
}

function Labels({ basis, cites, onCite }: { basis?: Basis | null; cites?: number[]; onCite: (number: number) => void }) {
  if (!basis && !(cites ?? []).length) {
    return null;
  }
  return (
    <>
      {' '}
      {basis ? <BasisChip basis={basis} className="align-middle" /> : null} <Cites cites={cites} onCite={onCite} />
    </>
  );
}

function ReportTable({ block, onCite }: { block: TableBlock; onCite: (number: number) => void }) {
  const rows = block.rows ?? [];
  const align = block.col_align ?? [];
  const cited = (block.row_cites ?? []).some((cites) => cites.length > 0);
  const right = (index: number) => align[index] === 'right';
  return (
    <figure className="space-y-2">
      <div
        className="relative overflow-x-auto rounded-panel border border-line"
        tabIndex={0}
        aria-label={`${block.caption}, scrolls sideways`}
      >
        <table className="w-full border-collapse text-small">
          <caption className="border-b border-line px-3 py-2 text-left text-small font-medium text-content">
            {block.caption}
          </caption>
          <thead className="bg-raised">
            <tr>
              {block.columns.map((column, index) => (
                <th
                  key={`${column}-${index}`}
                  scope="col"
                  className={cn(
                    'border-b border-line px-3 py-2 align-bottom font-medium text-content-secondary',
                    right(index) ? 'text-right' : 'text-left',
                    index === 0 && 'sticky left-0 z-10 min-w-[10rem] border-r bg-raised',
                  )}
                >
                  {column}
                </th>
              ))}
              {cited ? (
                <th scope="col" className="border-b border-line px-3 py-2 text-left font-medium text-content-secondary">
                  {SOURCES_COLUMN}
                </th>
              ) : null}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, rowIndex) => (
              <tr key={rowIndex} className="border-b border-line last:border-b-0">
                {row.map((cell, index) =>
                  index === 0 ? (
                    <th
                      key={index}
                      scope="row"
                      className={cn(
                        'sticky left-0 z-10 border-r border-line bg-surface px-3 py-2 align-top font-medium text-content',
                        right(index) ? 'text-right tabular' : 'text-left',
                      )}
                    >
                      {cell}
                    </th>
                  ) : (
                    <td
                      key={index}
                      className={cn(
                        'min-w-[8rem] bg-surface px-3 py-2 align-top text-content-secondary',
                        right(index) ? 'text-right tabular' : 'text-left',
                      )}
                    >
                      {cell}
                    </td>
                  ),
                )}
                {cited ? (
                  <td className="bg-surface px-3 py-2 align-top">
                    <Cites cites={block.row_cites?.[rowIndex]} onCite={onCite} />
                  </td>
                ) : null}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-micro text-content-muted lg:hidden">{REPORT_COPY.scrollHint}</p>
    </figure>
  );
}

export interface ReportBlockViewProps {
  block: ReportBlock;
  onCite: (number: number) => void;
}

export function ReportBlockView({ block, onCite }: ReportBlockViewProps) {
  switch (block.type) {
    case 'paragraph':
      return (
        <p className="max-w-prose text-body text-content-secondary">
          {block.text}
          <Labels basis={block.basis} cites={block.cites} onCite={onCite} />
        </p>
      );
    case 'bullets':
      return (
        <ul className="max-w-prose list-disc space-y-2 pl-6 text-body text-content-secondary">
          {(block.items ?? []).map((item, index) => (
            <li key={index}>
              {item.text}
              <Labels basis={item.basis} cites={item.cites} onCite={onCite} />
            </li>
          ))}
        </ul>
      );
    case 'table':
      return <ReportTable block={block} onCite={onCite} />;
    case 'callout': {
      const look = CALLOUT[block.kind];
      return (
        <div role="note" className={cn('flex max-w-prose items-start gap-3 rounded-panel border p-4', look.box)}>
          <look.Icon className={cn('mt-0.5 size-5 shrink-0', look.icon)} aria-hidden="true" />
          <p className="text-body text-content-secondary">
            <span className="font-medium text-content">{look.word}: </span>
            {block.text}
          </p>
        </div>
      );
    }
    case 'facts':
      return (
        <dl className="max-w-prose divide-y divide-line rounded-panel border border-line bg-surface text-small">
          {(block.pairs ?? []).map((pair, index) => (
            <div key={`${pair.label}-${index}`} className="flex flex-col gap-1 px-4 py-2 sm:flex-row sm:gap-6">
              <dt className="shrink-0 text-content-muted sm:w-56">{pair.label}</dt>
              <dd className="min-w-0 break-words text-content">{pair.value}</dd>
            </div>
          ))}
        </dl>
      );
    case 'subheading':
      return <h3>{block.text}</h3>;
    default:
      return null;
  }
}

export function ReportBlocks({ blocks, onCite }: { blocks: ReportBlock[] | undefined; onCite: (number: number) => void }) {
  return (
    <>
      {(blocks ?? []).map((block, index) => (
        <React.Fragment key={index}>
          <ReportBlockView block={block} onCite={onCite} />
        </React.Fragment>
      ))}
    </>
  );
}
