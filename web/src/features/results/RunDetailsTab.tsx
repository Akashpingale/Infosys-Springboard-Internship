/**
 * Run details tab (KIRO_UI_UPGRADE_SPEC.md Sections 7.4, 9 and 10.3).
 *
 * What the run itself did, for anyone checking the work: how long each stage took, every search it
 * made, every quality check that changed something, and the untouched JSON behind all of it.
 *
 * The raw JSON is the thing that makes the rest auditable, so it can be copied and saved. It is
 * built only when the panel is opened, because a full result runs to tens of thousands of
 * characters.
 */

import { AlertTriangle, Check, ChevronRight, Copy, Download, Info, XCircle } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import * as React from 'react';

import { EmptyState } from '@/components/EmptyState';
import { Button } from '@/components/ui/button';
import type { RunDetail } from '@/features/run/useRun';
import { StageTimings } from '@/features/results/StageTimings';
import { cn } from '@/lib/cn';
import { copyText, saveText } from '@/lib/download';
import { count } from '@/lib/format';
import { downloadName, noticeGroups, queryGroups, stageTiming } from '@/lib/runDetails';
import type { Notice, PipelineResult } from '@/lib/results';

const LOOK: Record<Notice['severity'], { Icon: LucideIcon; tone: string; word: string }> = {
  info: { Icon: Info, tone: 'text-info', word: 'Note' },
  warning: { Icon: AlertTriangle, tone: 'text-warning', word: 'Warning' },
  error: { Icon: XCircle, tone: 'text-danger', word: 'Error' },
};

export const COPY_DONE = 'The JSON was copied to the clipboard.';
export const COPY_FAILED = 'This browser would not let the page copy. Use Download instead.';
export const SAVE_FAILED = 'This browser would not let the page save a file.';

export interface RunDetailsTabProps {
  run: RunDetail;
  result: PipelineResult;
}

export function RunDetailsTab({ run, result }: RunDetailsTabProps) {
  const timing = React.useMemo(() => stageTiming(run), [run]);
  const queries = React.useMemo(() => queryGroups(result), [result]);
  const groups = React.useMemo(() => noticeGroups(result.notices ?? [], run.stages), [result.notices, run.stages]);

  const [jsonOpen, setJsonOpen] = React.useState(false);
  const [message, setMessage] = React.useState<string | null>(null);
  // Built only once the panel is open: a full result is tens of thousands of characters.
  const json = React.useMemo(() => (jsonOpen ? JSON.stringify(result, null, 2) : ''), [jsonOpen, result]);

  const totalQueries = queries.reduce((sum, group) => sum + group.rows.length, 0);
  const noticeCount = (result.notices ?? []).length;

  return (
    <div className="space-y-8">
      <StageTimings timing={timing} />

      <section aria-labelledby="queries-heading" className="space-y-4">
        <div className="space-y-1">
          <h3 id="queries-heading">Searches run</h3>
          <p className="max-w-prose text-small text-content-muted">
            {totalQueries === 0
              ? 'This run recorded no searches.'
              : `${count(totalQueries, 'search', 'searches')}, in the order the stages made them.`}
          </p>
        </div>

        {totalQueries === 0 ? (
          <EmptyState message="No search was recorded for this run." />
        ) : (
          <div className="space-y-4">
            {queries.map((group) => (
              <div key={group.stage} className="rounded-panel border border-line bg-surface">
                <p className="border-b border-line px-4 py-3 text-small font-medium text-content">{group.stage}</p>
                <ul className="divide-y divide-line">
                  {group.rows.map((row, index) => (
                    <li key={`${row.query}-${index}`} className="space-y-1 px-4 py-3">
                      <div className="flex flex-wrap items-baseline justify-between gap-3">
                        <p className="min-w-0 break-words font-mono text-micro text-content-secondary">
                          {row.query}
                        </p>
                        <span className="tabular shrink-0 text-micro text-content-muted">
                          {row.results === null ? 'Results not recorded' : count(row.results, 'result')}
                        </span>
                      </div>
                      {row.label ? <p className="text-micro text-content-muted">{row.label}</p> : null}
                      {row.error ? <p className="text-micro text-warning">This search failed: {row.error}</p> : null}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        )}
      </section>

      <section aria-labelledby="notices-heading" className="space-y-4">
        <div className="space-y-1">
          <h3 id="notices-heading">Quality checks</h3>
          <p className="max-w-prose text-small text-content-muted">
            {noticeCount === 0
              ? 'No check changed anything in this result.'
              : `${count(noticeCount, 'check')} adjusted this result, grouped by the stage that raised it.`}
          </p>
        </div>

        {groups.length === 0 ? (
          <EmptyState message="Nothing was removed, rewritten or left out by the checks." />
        ) : (
          <div className="space-y-4">
            {groups.map((group) => (
              <div key={group.stage} className="rounded-panel border border-line bg-surface">
                <p className="border-b border-line px-4 py-3 text-small font-medium text-content">
                  {group.stage}
                  <span className="tabular ml-2 text-content-muted">{group.notices.length}</span>
                </p>
                <ul className="divide-y divide-line">
                  {group.notices.map((notice, index) => {
                    const { Icon, tone, word } = LOOK[notice.severity];
                    return (
                      <li key={`${notice.code}-${index}`} className="flex items-start gap-3 px-4 py-3">
                        <Icon className={cn('mt-0.5 size-4 shrink-0', tone)} aria-hidden="true" />
                        <div className="min-w-0 flex-1 space-y-1">
                          <p className="max-w-prose text-body text-content-secondary">
                            <span className="sr-only">{word}: </span>
                            {notice.message}
                          </p>
                          <p className="font-mono text-micro text-content-muted">{notice.code}</p>
                          {notice.detail ? (
                            <details>
                              <summary className="flex min-h-[44px] cursor-pointer items-center text-micro text-content-muted sm:min-h-0">
                                Technical detail
                              </summary>
                              <p className="mt-1 break-words font-mono text-micro text-content-muted">
                                {notice.detail}
                              </p>
                            </details>
                          ) : null}
                        </div>
                      </li>
                    );
                  })}
                </ul>
              </div>
            ))}
          </div>
        )}
      </section>

      <section aria-labelledby="raw-json-heading" className="rounded-panel border border-line bg-surface">
        <details
          className="group"
          // Tens of thousands of characters: it is not opened for a printed page.
          data-print-keep-closed
          onToggle={(event) => setJsonOpen((event.currentTarget as HTMLDetailsElement).open)}
        >
          <summary className="flex cursor-pointer items-center gap-3 p-4 text-body text-content">
            <ChevronRight
              className="size-4 shrink-0 transition-transform duration-tab group-open:rotate-90"
              aria-hidden="true"
            />
            <span id="raw-json-heading" className="flex-1">
              Raw result JSON
            </span>
            <span className="text-small text-content-muted">Exactly what the backend returned</span>
          </summary>

          <div className="space-y-3 border-t border-line p-4">
            <div data-print-hide className="flex flex-col gap-3 sm:flex-row sm:flex-wrap">
              <Button
                variant="secondary"
                onClick={() => {
                  void copyText(json).then((ok) => setMessage(ok ? COPY_DONE : COPY_FAILED));
                }}
              >
                <Copy aria-hidden="true" />
                Copy JSON
              </Button>
              <Button
                variant="secondary"
                onClick={() => {
                  const ok = saveText(json, downloadName(run, 'json'), 'application/json');
                  setMessage(ok ? `Saved as ${downloadName(run, 'json')}.` : SAVE_FAILED);
                }}
              >
                <Download aria-hidden="true" />
                Download JSON
              </Button>
            </div>

            {message ? (
              <p role="status" className="flex items-center gap-2 text-small text-content-secondary">
                <Check className="size-4 shrink-0 text-success" aria-hidden="true" />
                {message}
              </p>
            ) : null}

            <pre className="max-h-96 overflow-auto rounded-control border border-line bg-canvas p-3 font-mono text-micro text-content-secondary">
              {json}
            </pre>
          </div>
        </details>
      </section>
    </div>
  );
}
