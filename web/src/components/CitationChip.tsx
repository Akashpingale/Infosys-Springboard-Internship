/**
 * Citation chips (KIRO_UI_UPGRADE_SPEC.md Section 8.6).
 *
 * The one memorable element: a claim is followed by a small numbered pill per source it cites.
 * The number replaces the evidence id, because "S10" means nothing to a reader. Hover or focus
 * shows the title and domain; clicking opens the drawer on that source.
 *
 * A claim taken from the founder's own words shows "From your idea" and no chip, because there is
 * no source to open. S0 is the search engine's summary, so its chip says so instead of a number.
 */

import { User } from 'lucide-react';

import type { Basis } from '@/components/BasisChip';
import { cn } from '@/lib/cn';
import { SUMMARY_CHIP_LABEL, type SourceRecord } from '@/lib/results';

export interface CitationChipProps {
  source: SourceRecord;
  onOpen: (key: string) => void;
  className?: string;
}

export function CitationChip({ source, onOpen, className }: CitationChipProps) {
  const name = source.isSummary ? SUMMARY_CHIP_LABEL : `Source ${source.number}: ${source.title}`;
  const hint = source.isSummary ? SUMMARY_CHIP_LABEL : `${source.title} \u2014 ${source.domain}`;
  return (
    <button
      type="button"
      onClick={() => onOpen(source.key)}
      title={hint}
      aria-label={`${name}. Open the source details.`}
      className={cn(
        /*
         * 24 px, which is the minimum for a target inside a sentence. Section 6.9 asks for 44 px on
         * touch, and WCAG 2.5.8 exempts a target in a line of text from that for the obvious
         * reason: a 44 px chip would break the line it sits in. Enlarging the hit area invisibly
         * was tried and rejected, because two chips side by side then overlap and the second one
         * swallows taps meant for the first.
         */
        'inline-flex h-6 min-w-6 shrink-0 items-center justify-center gap-1 rounded-pill border',
        'border-sourced-border bg-sourced-bg px-1.5 align-middle text-micro text-content',
        'transition-colors duration-tab hover:border-sourced hover:bg-raised',
        className,
      )}
    >
      {source.isSummary ? SUMMARY_CHIP_LABEL : source.number}
    </button>
  );
}

export interface CitationsProps {
  sources: SourceRecord[];
  onOpen: (key: string) => void;
  /** When the claim came from the founder, no chip is shown; this label is shown instead. */
  basis?: Basis | null;
  className?: string;
}

/** The chips after one claim, or the "from your idea" note when there is nothing to cite. */
export function Citations({ sources, onOpen, basis, className }: CitationsProps) {
  if (basis === 'user_provided') {
    return (
      <span className={cn('inline-flex items-center gap-1 align-middle text-micro text-content-muted', className)}>
        <User className="size-3.5" aria-hidden="true" />
        From your idea
      </span>
    );
  }
  if (sources.length === 0) {
    return null;
  }
  return (
    <span className={cn('inline-flex flex-wrap items-center gap-1 align-middle', className)}>
      {sources.map((source) => (
        <CitationChip key={source.key} source={source} onOpen={onOpen} />
      ))}
    </span>
  );
}
