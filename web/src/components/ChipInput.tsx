/**
 * Chip input (KIRO_UI_UPGRADE_SPEC.md Sections 2 finding 5, and 6.5).
 *
 * Target customers used to be one line that cut its own text off. Here each customer becomes a
 * chip: type and press Enter, or paste a comma-separated list. Backspace in an empty box removes
 * the last chip, which is what people expect from this control.
 *
 * Nothing is invented: the chips hold exactly what was typed, trimmed, with duplicates refused.
 */

import * as React from 'react';

import { Chip } from '@/components/Chip';
import { cn } from '@/lib/cn';

export const MAX_CHIPS = 8;
const SEPARATORS = /[,;\n]/;

export interface ChipInputProps {
  value: string[];
  onChange: (value: string[]) => void;
  id: string;
  placeholder?: string;
  max?: number;
  disabled?: boolean;
  onBlur?: () => void;
  'aria-describedby'?: string | undefined;
  'aria-invalid'?: boolean | undefined;
  'aria-required'?: boolean | undefined;
}

export function ChipInput({
  value,
  onChange,
  id,
  placeholder,
  max = MAX_CHIPS,
  disabled,
  onBlur,
  ...aria
}: ChipInputProps) {
  const [draft, setDraft] = React.useState('');
  const full = value.length >= max;

  const add = React.useCallback(
    (raw: string) => {
      const additions = raw
        .split(SEPARATORS)
        .map((part) => part.trim())
        .filter(Boolean);
      if (additions.length === 0) {
        return;
      }
      const next = [...value];
      for (const addition of additions) {
        const duplicate = next.some((kept) => kept.toLowerCase() === addition.toLowerCase());
        if (!duplicate && next.length < max) {
          next.push(addition);
        }
      }
      if (next.length !== value.length) {
        onChange(next);
      }
      setDraft('');
    },
    [max, onChange, value],
  );

  function onKeyDown(event: React.KeyboardEvent<HTMLInputElement>): void {
    if (event.key === 'Enter') {
      // Enter adds a chip; it must not submit the form from here.
      event.preventDefault();
      add(draft);
      return;
    }
    if (event.key === 'Backspace' && draft === '' && value.length > 0) {
      event.preventDefault();
      onChange(value.slice(0, -1));
    }
  }

  return (
    <div
      className={cn(
        'flex min-h-[44px] flex-wrap items-center gap-2 rounded-control border border-line-strong',
        'bg-raised px-3 py-2 transition-colors duration-tab',
        'focus-within:border-primary',
        aria['aria-invalid'] ? 'border-danger' : '',
        disabled ? 'cursor-not-allowed opacity-50' : '',
      )}
    >
      {value.map((entry) => (
        <Chip key={entry} removeLabel={entry} onRemove={() => onChange(value.filter((kept) => kept !== entry))}>
          {entry}
        </Chip>
      ))}
      <input
        id={id}
        type="text"
        value={draft}
        disabled={disabled || full}
        placeholder={value.length === 0 ? placeholder : full ? '' : 'Add another'}
        onChange={(event) => setDraft(event.target.value)}
        onKeyDown={onKeyDown}
        onBlur={() => {
          // Whatever is still typed counts, so a value is not lost by clicking away.
          add(draft);
          onBlur?.();
        }}
        className={cn(
          'min-w-[12ch] flex-1 bg-transparent text-body text-content outline-none',
          'placeholder:text-content-muted disabled:cursor-not-allowed',
          // 44 px to tap into on a touch screen (Section 6.9); the row itself sets the height above.
          'min-h-[44px] sm:min-h-0',
        )}
        {...aria}
      />
    </div>
  );
}
