import { ExternalLink } from 'lucide-react';

import { REPORT_COPY } from '@/features/report/copy';
import { sourceAnchor } from '@/features/report/ReportBlocks';
import type { BibEntry } from '@/features/report/useReport';

const WEB_ADDRESS = /^https?:\/\//i;

export function webAddress(url: string | null | undefined): string | null {
  return url && WEB_ADDRESS.test(url) ? url : null;
}

export interface ReportBibliographyProps {
  entries: BibEntry[];
  sectionTitles: Map<string, string>;
}

export function ReportBibliography({ entries, sectionTitles }: ReportBibliographyProps) {
  if (entries.length === 0) {
    return null;
  }
  return (
    <ol aria-label="Numbered sources" className="max-w-prose space-y-3">
      {entries.map((entry) => {
        const link = webAddress(entry.url);
        const cited = (entry.cited_in ?? []).map((id) => sectionTitles.get(id) ?? id);
        return (
          <li
            key={entry.number}
            id={sourceAnchor(entry.number)}
            tabIndex={-1}
            className="flex gap-3 rounded-panel border border-line bg-surface p-4"
          >
            <span className="tabular shrink-0 text-body text-content-muted">{entry.number}.</span>
            <div className="min-w-0 space-y-1">
              <p className="break-words text-body text-content">{entry.title}</p>
              {entry.domain ? <p className="text-micro text-content-muted">{entry.domain}</p> : null}
              {link ? (
                <a
                  href={link}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex min-h-[44px] items-center gap-1 break-all text-small text-primary underline underline-offset-2 hover:text-primary-hover sm:min-h-0"
                >
                  {link}
                  <ExternalLink className="size-3.5 shrink-0" aria-hidden="true" />
                  <span className="sr-only"> (opens in a new tab)</span>
                </a>
              ) : entry.url ? (
                <p className="break-all text-small text-content-secondary">{entry.url}</p>
              ) : null}
              {entry.has_page ? null : <p className="text-small text-content-secondary">{REPORT_COPY.engineSummary}</p>}
              {cited.length > 0 ? (
                <p className="text-micro text-content-muted">Cited in: {cited.join(', ')}.</p>
              ) : null}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
