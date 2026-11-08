/**
 * The app shell (KIRO_UI_UPGRADE_SPEC.md Sections 5, 6.4 and 6.9).
 *
 * A top bar with the product name and the three destinations, then the page. The skip link is the
 * first thing in the tab order, and <main> carries the id it jumps to.
 */

import * as React from 'react';
import { NavLink, Outlet } from 'react-router-dom';

import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/cn';

const DESTINATIONS = [
  { to: '/', label: 'New validation' },
  { to: '/history', label: 'History' },
  { to: '/status', label: 'Status' },
] as const;

/** The wait while a screen's code arrives. Announced, so it is not a silent blank page. */
function ScreenLoading() {
  return (
    <div className="space-y-6" aria-busy="true">
      <p role="status" className="sr-only">
        Loading the page.
      </p>
      <Skeleton className="h-9 w-72" />
      <div className="space-y-3 rounded-panel border border-line bg-surface p-6">
        {[0, 1, 2].map((row) => (
          <Skeleton key={row} className="h-10 w-full" />
        ))}
      </div>
    </div>
  );
}

export function AppShell() {
  return (
    <div className="min-h-screen bg-canvas">
      <a href="#main" className="skip-link min-h-[44px] sm:min-h-0">
        Skip to main content
      </a>

      <header className="border-b border-line bg-surface">
        {/*
          The bar stacks on a narrow screen. At a fixed 64 px the product name wrapped onto three
          lines and spilled out of the header at 390 px, so instead the name takes its own line
          there and the destinations sit beneath it.
        */}
        <nav
          aria-label="Main"
          className={cn(
            'mx-auto flex max-w-app flex-col gap-2 px-4 py-3',
            'sm:h-16 sm:flex-row sm:items-center sm:justify-between sm:gap-6 sm:px-6 sm:py-0',
          )}
        >
          <NavLink
            to="/"
            className="inline-flex min-h-[44px] items-center font-condensed text-h2 text-content sm:min-h-0"
          >
            Startup Idea Validator
          </NavLink>
          <ul className="flex flex-wrap items-center gap-2">
            {DESTINATIONS.map(({ to, label }) => (
              <li key={to}>
                <NavLink
                  to={to}
                  end={to === '/'}
                  className={({ isActive }) =>
                    cn(
                      'inline-flex h-10 min-h-[44px] items-center rounded-control px-3 text-body',
                      'transition-colors duration-tab sm:min-h-10',
                      isActive
                        ? 'bg-raised text-content'
                        : 'text-content-secondary hover:bg-raised hover:text-content',
                    )
                  }
                >
                  {label}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>
      </header>

      <main id="main" className="mx-auto max-w-app px-4 py-8 sm:px-6">
        {/* Each screen is a separate download (router.tsx), so one may briefly not be here yet. */}
        <React.Suspense fallback={<ScreenLoading />}>
          <Outlet />
        </React.Suspense>
      </main>
    </div>
  );
}
