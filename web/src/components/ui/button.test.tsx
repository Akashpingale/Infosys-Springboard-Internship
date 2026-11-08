import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { Button } from '@/components/ui/button';

describe('Button', () => {
  it('calls its handler when clicked', async () => {
    const onClick = vi.fn();
    render(<Button onClick={onClick}>Review my idea</Button>);

    await userEvent.click(screen.getByRole('button', { name: 'Review my idea' }));

    expect(onClick).toHaveBeenCalledOnce();
  });

  it('blocks the click and marks itself busy while a request is in flight', async () => {
    const onClick = vi.fn();
    render(
      <Button loading onClick={onClick}>
        Validating
      </Button>,
    );

    const button = screen.getByRole('button', { name: /validating/i });
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute('aria-busy', 'true');

    await userEvent.click(button);
    expect(onClick).not.toHaveBeenCalled();
  });

  it('renders as a link when asked, so a navigation keeps its own semantics', () => {
    render(
      <Button asChild>
        <a href="/history">History</a>
      </Button>,
    );

    expect(screen.getByRole('link', { name: 'History' })).toHaveAttribute('href', '/history');
    expect(screen.queryByRole('button')).not.toBeInTheDocument();
  });

  it('keeps a touch-sized target at the default size', () => {
    render(<Button>Start</Button>);
    expect(screen.getByRole('button', { name: 'Start' }).className).toContain('min-h-[44px]');
  });
});
