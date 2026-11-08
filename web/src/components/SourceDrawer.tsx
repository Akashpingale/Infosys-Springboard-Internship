/**
 * Source drawer (KIRO_UI_UPGRADE_SPEC.md Sections 6.5, 6.9 and 8.6).
 *
 * A panel on the right, or a sheet along the bottom on a narrow screen. It shows one source and
 * every claim in the result that cites it, so a reader can see what rests on it.
 *
 * It is a native <dialog> opened with showModal(). The browser supplies the focus trap, Escape to
 * close and returning focus to whatever opened it, which is what Section 6.9 requires of a drawer;
 * doing it this way needs no extra dependency.
 */

import { ExternalLink, X } from 'lucide-react';
import * as React from 'react';

import { BasisChip } from '@/components/BasisChip';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/cn';
import { SUMMARY_EXPLANATION, type Claim, type SourceRecord } from '@/lib/results';

export interface SourceDrawerProps {
  /** The source to show, or null when the drawer is closed. */
  source: SourceRecord | null;
  /** The claims that cite it, already filtered. */
  citedBy: Claim[];
  onClose: () => void;
}

export function SourceDrawer({ source, citedBy, onClose }: SourceDrawerProps) {
  const ref = React.useRef<HTMLDialogElement>(null);

  React.useEffect(() => {
    const dialog = ref.current;
    if (!dialog) {
      return;
    }
    if (source && !dialog.open) {
      // showModal gives the focus trap and Escape handling; a plain open attribute does not.
      if (typeof dialog.showModal === 'function') {
        dialog.showModal();
      } else {
        dialog.setAttribute('open', '');
      }
    }
    if (!source && dialog.open) {
      dialog.close();
    }
  }, [source]);

  /*
   * A modal dialog closes on Escape by itself, but the fallback above opens it without a modal, and
   * then nothing would. Handling the key here closes the drawer either way.
   */
  React.useEffect(() => {
    if (!source) {
      return;
    }
    function onKeyDown(event: KeyboardEvent): void {
      if (event.key === 'Escape') {
        event.preventDefault();
        onClose();
      }
    }
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [source, onClose]);

  if (!source) {
    return null;
  }

  return (
    <dialog
      ref={ref}
      aria-labelledby="source-drawer-title"
      onCancel={(event) => {
        // Escape: let the page decide, so its state and the dialog stay in step.
        event.preventDefault();
        onClose();
      }}
      onClick={(event) => {
        if (event.target === ref.current) {
          onClose();
        }
      }}
      className={cn(
        'm-0 max-h-none max-w-none bg-transparent p-0 backdrop:bg-black/60',
        // Bottom sheet on a narrow screen, right-hand panel from the small breakpoint up.
        'fixed inset-x-0 bottom-0 top-auto w-full sm:inset-y-0 sm:left-auto sm:right-0 sm:w-[28rem]',
      )}
    >
      <div
        className={cn(
          'flex max-h-[85vh] flex-col gap-4 overflow-y-auto border border-line bg-surface p-6',
          'rounded-t-panel shadow-overlay sm:h-screen sm:max-h-none sm:rounded-none sm:rounded-l-panel',
        )}
      >
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0 space-y-1">
            <p className="text-micro text-content-muted">
              {source.isSummary ? 'Search summary' : `Source ${source.number}`}
            </p>
            <h2 id="source-drawer-title" className="break-words">
              {source.title}
            </h2>
            {source.domain ? <p className="font-mono text-small text-content-muted">{source.domain}</p> : null}
          </div>
          <Button variant="secondary" size="icon" onClick={onClose} aria-label="Close the source details">
            <X aria-hidden="true" />
          </Button>
        </div>

        {source.isSummary ? (
          <p className="max-w-prose text-body text-content-secondary">{SUMMARY_EXPLANATION}</p>
        ) : (
          <Button asChild variant="secondary" className="self-start">
            <a href={source.url} target="_blank" rel="noreferrer noopener">
              <ExternalLink aria-hidden="true" />
              Open source
            </a>
          </Button>
        )}

        <div className="space-y-3 border-t border-line pt-4">
          <h3>
            {citedBy.length === 0
              ? 'Nothing in this result cites it'
              : `Cited by ${citedBy.length === 1 ? '1 finding' : `${citedBy.length} findings`}`}
          </h3>
          {citedBy.length === 0 ? (
            <p className="max-w-prose text-small text-content-muted">
              It was collected during the research but no finding rests on it.
            </p>
          ) : (
            <ul className="space-y-4">
              {citedBy.map((claim, index) => (
                <li key={`${claim.where}-${index}`} className="space-y-2">
                  <p className="text-micro text-content-muted">{claim.where}</p>
                  <p className="text-body text-content-secondary">{claim.text}</p>
                  {claim.basis ? <BasisChip basis={claim.basis} /> : null}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </dialog>
  );
}
