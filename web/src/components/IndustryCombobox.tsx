/**
 * Industry combobox (KIRO_UI_UPGRADE_SPEC.md Sections 2 finding 4, and 6.5).
 *
 * The old form had a fixed list plus a separate "If Other, specify" box that was always on screen.
 * Here one control does both: the list is searchable, and whatever is typed can be used as it
 * stands through a "Use your own" option, so the rare case costs no permanent field.
 *
 * The industries come from GET /api/meta, never from a list copied into the front end. The
 * specification's own "Other" entry is left out of the choices, because typing a value replaces it.
 */

import { Check, ChevronsUpDown } from 'lucide-react';
import * as React from 'react';

import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from '@/components/ui/command';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { cn } from '@/lib/cn';

/** The catch-all entry in models/schemas.INDUSTRIES; typing a value takes its place. */
export const OTHER_INDUSTRY = 'Other';
export const PLACEHOLDER = 'Search or type your industry';

export interface IndustryComboboxProps {
  value: string;
  onChange: (value: string) => void;
  /** The list from /api/meta. Empty while it loads, which disables the control. */
  industries: string[];
  id: string;
  'aria-describedby'?: string | undefined;
  'aria-invalid'?: boolean | undefined;
  'aria-required'?: boolean | undefined;
  disabled?: boolean;
  onBlur?: () => void;
}

export function IndustryCombobox({
  value,
  onChange,
  industries,
  id,
  disabled,
  onBlur,
  ...aria
}: IndustryComboboxProps) {
  const [open, setOpen] = React.useState(false);
  const [search, setSearch] = React.useState('');

  const choices = React.useMemo(
    () => industries.filter((industry) => industry !== OTHER_INDUSTRY),
    [industries],
  );
  const typed = search.trim();
  // Offer the typed value only when it is not already one of the choices.
  const canUseTyped =
    typed.length > 0 && !choices.some((choice) => choice.toLowerCase() === typed.toLowerCase());

  function choose(next: string): void {
    onChange(next);
    setSearch('');
    setOpen(false);
    onBlur?.();
  }

  return (
    <Popover
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (!next) {
          onBlur?.();
        }
      }}
    >
      <PopoverTrigger
        id={id}
        type="button"
        role="combobox"
        aria-expanded={open}
        disabled={disabled || industries.length === 0}
        className={cn(
          'flex h-10 min-h-[44px] w-full items-center justify-between gap-2 sm:min-h-10',
          'rounded-control border border-line-strong bg-raised px-3 text-body',
          'transition-colors duration-tab hover:border-primary',
          'aria-[invalid=true]:border-danger',
          'disabled:cursor-not-allowed disabled:opacity-50',
          value ? 'text-content' : 'text-content-muted',
        )}
        {...aria}
      >
        <span className="truncate">{value || PLACEHOLDER}</span>
        <ChevronsUpDown className="size-4 shrink-0 text-content-muted" aria-hidden="true" />
      </PopoverTrigger>

      <PopoverContent>
        <Command
          // The typed text decides what counts, so cmdk's own filtering is left on for the list.
          loop
        >
          <CommandInput placeholder={PLACEHOLDER} value={search} onValueChange={setSearch} />
          <CommandList>
            {!canUseTyped ? <CommandEmpty>No industry matches that. Keep typing to use your own.</CommandEmpty> : null}
            {canUseTyped ? (
              <CommandGroup>
                <CommandItem value={`use-your-own-${typed}`} onSelect={() => choose(typed)}>
                  Use your own: <span className="font-medium">{typed}</span>
                </CommandItem>
              </CommandGroup>
            ) : null}
            <CommandGroup>
              {choices.map((industry) => (
                <CommandItem key={industry} value={industry} onSelect={() => choose(industry)}>
                  <Check
                    className={cn('size-4 shrink-0', industry === value ? 'text-primary' : 'opacity-0')}
                    aria-hidden="true"
                  />
                  {industry}
                </CommandItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
