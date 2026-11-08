/**
 * Quality notes (KIRO_UI_UPGRADE_SPEC.md Sections 6.7 and 10.3).
 *
 * The old interface put three amber warnings above the idea, each naming an internal field such as
 * `market_demand.demand_evidence[1]`. These are the backend's `notices`, whose `message` is written
 * for the reader; the panel is collapsed by default and the technical text stays behind "Show
 * details" for whoever is developing.
 */

import { AlertTriangle, ChevronRight, Info, XCircle } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';

import { cn } from '@/lib/cn';
import type { Notice } from '@/lib/results';

const LOOK: Record<Notice['severity'], { Icon: LucideIcon; tone: string; word: string }> = {
  info: { Icon: Info, tone: 'text-info', word: 'Note' },
  warning: { Icon: AlertTriangle, tone: 'text-warning', word: 'Warning' },
  error: { Icon: XCircle, tone: 'text-danger', word: 'Error' },
};

export function noticesHeading(notices: Notice[]): string {
  const checks = notices.length === 1 ? '1 quality check' : `${notices.length} quality checks`;
  return `${checks} adjusted these results`;
}

export interface QualityNotesProps {
  notices: Notice[];
  className?: string;
}

export function QualityNotes({ notices, className }: QualityNotesProps) {
  if (notices.length === 0) {
    return null;
  }

  return (
    <section
      aria-labelledby="quality-notes-heading"
      className={cn('rounded-panel border border-line bg-surface', className)}
    >
      <details className="group">
        <summary className="flex cursor-pointer items-center gap-3 p-4 text-body text-content">
          <ChevronRight
            className="size-4 shrink-0 transition-transform duration-tab group-open:rotate-90"
            aria-hidden="true"
          />
          <span id="quality-notes-heading" className="flex-1">
            {noticesHeading(notices)}
          </span>
          <span className="text-small text-content-muted group-open:hidden">Show details</span>
          <span className="hidden text-small text-content-muted group-open:inline">Hide details</span>
        </summary>

        <ul className="space-y-4 border-t border-line p-4">
          {notices.map((notice, index) => {
            const { Icon, tone, word } = LOOK[notice.severity];
            return (
              <li key={`${notice.code}-${index}`} className="flex items-start gap-3">
                <Icon className={cn('mt-0.5 size-4 shrink-0', tone)} aria-hidden="true" />
                <div className="min-w-0 flex-1 space-y-1">
                  <p className="max-w-prose text-body text-content-secondary">
                    <span className="sr-only">{word}: </span>
                    {notice.message}
                  </p>
                  {notice.detail ? (
                    <details>
                      <summary className="flex min-h-[44px] cursor-pointer items-center text-micro text-content-muted sm:min-h-0">
                        Technical detail
                      </summary>
                      <p className="mt-1 break-words font-mono text-micro text-content-muted">{notice.detail}</p>
                    </details>
                  ) : null}
                </div>
              </li>
            );
          })}
        </ul>
      </details>
    </section>
  );
}
