/**
 * Error boundary (KIRO_UI_UPGRADE_SPEC.md Section 6.5): a plain page with a reload action. A stack
 * trace is never shown to the user; it goes to the browser console for a developer.
 */

import * as React from 'react';

import { Button } from '@/components/ui/button';

interface State {
  failed: boolean;
}

export class ErrorBoundary extends React.Component<{ children: React.ReactNode }, State> {
  state: State = { failed: false };

  static getDerivedStateFromError(): State {
    return { failed: true };
  }

  componentDidCatch(error: unknown): void {
    // The console is for whoever is developing; the page below stays plain.
    console.error('The interface stopped unexpectedly.', error);
  }

  render(): React.ReactNode {
    if (!this.state.failed) {
      return this.props.children;
    }
    return (
      <main className="mx-auto flex max-w-form flex-col items-start gap-4 px-4 py-16 sm:px-6">
        <h1>Something went wrong on this page</h1>
        <p className="max-w-prose text-body text-content-secondary">
          The page stopped before it finished loading. Reloading usually fixes it. Your saved
          validations are not affected.
        </p>
        <Button onClick={() => window.location.reload()}>Reload the page</Button>
      </main>
    );
  }
}
