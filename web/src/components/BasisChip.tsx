/**
 * Basis chip (KIRO_UI_UPGRADE_SPEC.md Sections 6.2 and 6.5).
 *
 * How a claim is grounded, always as an icon plus a word, with the colour only reinforcing it. The
 * label text is rendered in the normal text colour rather than the basis colour: Section 6.2 notes
 * that two of these four colours fall below 3:1 in light mode, and as label text two of them also
 * miss 4.5:1 on their own tint in dark mode. The icon and the border carry the colour, so the
 * palette is unchanged and the words stay readable in both themes.
 */

import { CircleHelp, Link2, Sparkles, User } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';

import { cn } from '@/lib/cn';

export type Basis = 'sourced' | 'ai_interpretation' | 'user_provided' | 'assumption';

interface Appearance {
  label: string;
  Icon: LucideIcon;
  wrapper: string;
  icon: string;
}

/** Section 6.2: these four words, exactly. */
const APPEARANCE: Record<Basis, Appearance> = {
  sourced: {
    label: 'Sourced',
    Icon: Link2,
    wrapper: 'bg-sourced-bg border-sourced-border',
    icon: 'text-sourced',
  },
  ai_interpretation: {
    label: 'AI interpretation',
    Icon: Sparkles,
    wrapper: 'bg-interpretation-bg border-interpretation-border',
    icon: 'text-interpretation',
  },
  user_provided: {
    label: 'From your idea',
    Icon: User,
    wrapper: 'bg-provided-bg border-provided-border',
    icon: 'text-provided',
  },
  assumption: {
    label: 'Assumption',
    Icon: CircleHelp,
    wrapper: 'bg-assumption-bg border-assumption-border',
    icon: 'text-assumption',
  },
};

export const BASIS_LABELS: Record<Basis, string> = {
  sourced: APPEARANCE.sourced.label,
  ai_interpretation: APPEARANCE.ai_interpretation.label,
  user_provided: APPEARANCE.user_provided.label,
  assumption: APPEARANCE.assumption.label,
};

export interface BasisChipProps {
  basis: Basis;
  className?: string;
}

export function BasisChip({ basis, className }: BasisChipProps) {
  const { label, Icon, wrapper, icon } = APPEARANCE[basis];
  return (
    <span
      className={cn(
        'inline-flex h-6 items-center gap-2 rounded-pill border px-3 text-micro text-content',
        wrapper,
        className,
      )}
    >
      <Icon className={cn('size-3.5 shrink-0', icon)} aria-hidden="true" />
      {label}
    </span>
  );
}
