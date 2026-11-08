/**
 * The app shell and the routes.
 *
 * Every screen is loaded on its own since Prompt J (router.tsx), so a page arrives after a tick
 * rather than on the first render. The assertions wait for it, which is also what proves the
 * waiting state does not leave the reader on a blank page.
 */

import { screen } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import * as React from 'react';
import { Route, Routes } from 'react-router-dom';
import { beforeAll, describe, expect, it } from 'vitest';

import { API_URL } from '@/api/client';
import { AppShell } from '@/app/AppShell';
import { AppRoutes } from '@/app/router';
import { META } from '@/test/fixtures';
import { renderWithApp } from '@/test/render';
import { server } from '@/test/server';

/*
 * The screens are loaded on demand in the browser, and vitest compiles each one the first time it
 * is imported. Doing that here, before the tests, means a test measures the router rather than the
 * compiler: the form's module graph alone takes several seconds on a busy machine. The routes are
 * still the real lazy routes, and the same module cache answers them.
 */
beforeAll(async () => {
  await Promise.all([
    import('@/features/new-validation/NewValidationPage'),
    import('@/features/history/HistoryPage'),
    import('@/features/status/StatusPage'),
    import('@/features/not-found/NotFoundPage'),
  ]);
}, 180000);

/** The screens read these as they mount; the shell itself reads nothing. */
function backendUp() {
  server.use(
    http.get(`${API_URL}/api/meta`, () => HttpResponse.json(META)),
    http.get(`${API_URL}/health`, () => HttpResponse.json({ status: 'ok' })),
    http.get(`${API_URL}/api/runs`, () => HttpResponse.json({ runs: [] })),
  );
}

describe('App shell', () => {
  it('offers a skip link that points at the main region', () => {
    backendUp();
    renderWithApp(<AppRoutes />);

    const skip = screen.getByRole('link', { name: /skip to main content/i });
    expect(skip).toHaveAttribute('href', '#main');
    expect(document.getElementById('main')?.tagName).toBe('MAIN');
  });

  it('names its navigation and lists the three destinations', () => {
    backendUp();
    renderWithApp(<AppRoutes />);

    const nav = screen.getByRole('navigation', { name: 'Main' });
    expect(nav).toBeInTheDocument();
    for (const label of ['New validation', 'History', 'Status']) {
      expect(screen.getByRole('link', { name: label })).toBeInTheDocument();
    }
  });

  it('keeps the navigation on screen, and says it is loading, while a screen is still arriving', () => {
    /*
     * A screen that never finishes loading, so the waiting state can be checked without depending
     * on how long a real chunk takes: under load that timing is the machine's, not the shell's.
     */
    const Pending = React.lazy(() => new Promise<never>(() => {}));
    renderWithApp(
      <Routes>
        <Route element={<AppShell />}>
          <Route index element={<Pending />} />
        </Route>
      </Routes>,
    );

    expect(screen.getByRole('navigation', { name: 'Main' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /skip to main content/i })).toBeInTheDocument();
    expect(screen.getByRole('status')).toHaveTextContent(/loading the page/i);
    expect(document.querySelector('[aria-busy="true"]')).toBeInTheDocument();
  });

  it('shows the new validation page at the root', async () => {
    backendUp();
    renderWithApp(<AppRoutes />);
    expect(
      await screen.findByRole(
        'heading',
        { level: 1, name: /check your startup idea/i },
        { timeout: 20000 },
      ),
    ).toBeInTheDocument();
  }, 30000);

  it.each([
    ['/history', /history/i],
    ['/status', /system status/i],
  ])('renders %s', async (route, heading) => {
    backendUp();
    renderWithApp(<AppRoutes />, { route });
    expect(
      await screen.findByRole('heading', { level: 1, name: heading }, { timeout: 20000 }),
    ).toBeInTheDocument();
  }, 30000);

  it('explains an unknown address instead of showing a blank page', async () => {
    backendUp();
    renderWithApp(<AppRoutes />, { route: '/nowhere' });
    expect(
      await screen.findByRole(
        'heading',
        { level: 1, name: /that page does not exist/i },
        { timeout: 20000 },
      ),
    ).toBeInTheDocument();
  }, 30000);
});
