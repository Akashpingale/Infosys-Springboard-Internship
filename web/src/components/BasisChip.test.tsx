import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { BASIS_LABELS, BasisChip, type Basis } from '@/components/BasisChip';

const ALL: Basis[] = ['sourced', 'ai_interpretation', 'user_provided', 'assumption'];

describe('BasisChip', () => {
  it('writes out the four bases in the words the specification gives', () => {
    expect(BASIS_LABELS).toEqual({
      sourced: 'Sourced',
      ai_interpretation: 'AI interpretation',
      user_provided: 'From your idea',
      assumption: 'Assumption',
    });
  });

  it.each(ALL)('shows a word for %s, so colour is never the only signal', (basis) => {
    render(<BasisChip basis={basis} />);
    expect(screen.getByText(BASIS_LABELS[basis])).toBeInTheDocument();
  });

  it('hides its icon from assistive technology, because the word already says it', () => {
    const { container } = render(<BasisChip basis="sourced" />);
    const icon = container.querySelector('svg');
    expect(icon).not.toBeNull();
    expect(icon).toHaveAttribute('aria-hidden', 'true');
  });

  it('keeps the label in the normal text colour, so it stays readable in both themes', () => {
    render(<BasisChip basis="ai_interpretation" />);
    expect(screen.getByText('AI interpretation')).toHaveClass('text-content');
  });
});
