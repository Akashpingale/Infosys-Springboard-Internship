import { ChevronDown } from 'lucide-react';
import * as React from 'react';

import { cn } from '@/lib/cn';
import { NARROW, useMediaQuery } from '@/lib/useMediaQuery';

export interface TocEntry {
  id: string;
  title: string;
}

export function sectionAnchor(id: string): string {
  return `report-${id}`;
}

export interface ReportTocProps {
  entries: TocEntry[];
  current: string | null;
  onSelect: (id: string) => void;
}

function Links({ entries, current, onSelect }: ReportTocProps) {
  return (
    <>
      {entries.map((entry) => {
        const here = entry.id === current;
        return (
          <li key={entry.id}>
            <a
              href={`#${sectionAnchor(entry.id)}`}
              aria-current={here ? 'location' : undefined}
              onClick={(event) => {
                event.preventDefault();
                onSelect(entry.id);
              }}
              className={cn(
                'flex min-h-[44px] items-center border-l-2 px-3 text-small transition-colors duration-tab sm:min-h-10',
                here
                  ? 'border-primary text-content'
                  : 'border-transparent text-content-secondary hover:text-content',
              )}
            >
              {entry.title}
            </a>
          </li>
        );
      })}
    </>
  );
}

export function ReportToc({ entries, current, onSelect }: ReportTocProps) {
  const narrow = useMediaQuery(NARROW);
  const [open, setOpen] = React.useState(false);
  const listId = React.useId();

  if (narrow) {
    return (
      <nav aria-label="Contents" data-report-toc className="rounded-panel border border-line bg-surface">
        <button
          type="button"
          aria-expanded={open}
          aria-controls={listId}
          onClick={() => setOpen((value) => !value)}
          className="flex min-h-[44px] w-full items-center justify-between gap-3 px-4 text-body text-content"
        >
          Contents
          <ChevronDown
            className={cn('size-4 shrink-0 transition-transform duration-tab', open && 'rotate-180')}
            aria-hidden="true"
          />
        </button>
        <ol id={listId} hidden={!open} data-report-toc-list className="border-t border-line py-2">
          <Links
            entries={entries}
            current={current}
            onSelect={(id) => {
              setOpen(false);
              onSelect(id);
            }}
          />
        </ol>
      </nav>
    );
  }

  return (
    <nav aria-label="Contents" data-report-toc className="sticky top-6 max-h-[calc(100vh-3rem)] overflow-y-auto">
      <p className="px-3 pb-2 text-small font-medium text-content-muted">Contents</p>
      <ol>
        <Links entries={entries} current={current} onSelect={onSelect} />
      </ol>
    </nav>
  );
}
