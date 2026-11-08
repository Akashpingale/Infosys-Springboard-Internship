/**
 * Chip (KIRO_UI_UPGRADE_SPEC.md Section 6.5).
 *
 * A small, neutral pill. With `onRemove` it carries a remove button whose accessible name says
 * what it removes, which the target-customers chip input uses in Prompt E.
 */

import { X } from 'lucide-react';

import { cn } from '@/lib/cn';

export interface ChipProps {
  children: React.ReactNode;
  /** Shown as a removable chip when given. */
  onRemove?: () => void;
  /** What the remove button announces, for example "Small farmers". */
  removeLabel?: string;
  className?: string;
}

export function Chip({ children, onRemove, removeLabel, className }: ChipProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-2 rounded-pill border border-line bg-raised px-3',
        'text-micro text-content',
        // A removable chip is taller on a touch screen, so its remove button can be a 44 px target
        // without an invisible overlay that would steal taps from the chip beside it (Section 6.9).
        onRemove ? 'h-11 sm:h-6' : 'h-6',
        className,
      )}
    >
      {children}
      {onRemove ? (
        <button
          type="button"
          onClick={onRemove}
          className={cn(
            '-mr-2 flex size-11 items-center justify-center rounded-pill sm:-mr-1 sm:size-4',
            'text-content-muted hover:text-content',
          )}
          aria-label={`Remove ${removeLabel ?? String(children)}`}
        >
          <X className="size-3.5 shrink-0" aria-hidden="true" />
        </button>
      ) : null}
    </span>
  );
}
