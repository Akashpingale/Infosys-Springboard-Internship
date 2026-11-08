/**
 * Test helpers: render a component inside the providers and a router, with a fresh query cache for
 * every test so one test cannot see another's data.
 */

import { QueryClient } from '@tanstack/react-query';
import { render, type RenderOptions, type RenderResult } from '@testing-library/react';
import type * as React from 'react';
import { MemoryRouter } from 'react-router-dom';

import { Providers } from '@/app/providers';

export function testQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0, staleTime: 0 },
      mutations: { retry: false },
    },
  });
}

export interface RenderWithAppOptions extends Omit<RenderOptions, 'wrapper'> {
  route?: string;
  /** Router state, for a screen reached with navigate(path, { state }), such as edit and re-run. */
  state?: unknown;
  client?: QueryClient;
}

export function renderWithApp(
  ui: React.ReactNode,
  { route = '/', state, client, ...options }: RenderWithAppOptions = {},
): RenderResult {
  return render(
    <Providers client={client ?? testQueryClient()}>
      <MemoryRouter initialEntries={[state === undefined ? route : { pathname: route, state }]}>
        {ui}
      </MemoryRouter>
    </Providers>,
    options,
  );
}
