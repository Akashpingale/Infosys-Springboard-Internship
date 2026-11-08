/**
 * Providers (KIRO_UI_UPGRADE_SPEC.md Sections 3.1 and 8.2).
 *
 * TanStack Query holds the server state. A request is not retried when the backend answered with a
 * reason of its own, because repeating it would only repeat the same answer; a lost connection is
 * retried twice, which is what Section 8.2 asks of polling.
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import * as React from 'react';
import { Toaster } from 'sonner';

import { ApiError } from '@/api/client';

const MAX_OFFLINE_RETRIES = 2;

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 10_000,
        refetchOnWindowFocus: false,
        retry: (failureCount, error) => {
          if (error instanceof ApiError && !error.isOffline) {
            return false;
          }
          return failureCount < MAX_OFFLINE_RETRIES;
        },
      },
      mutations: { retry: false },
    },
  });
}

export function Providers({
  children,
  client,
}: {
  children: React.ReactNode;
  /** Tests pass their own client so each test starts with an empty cache. */
  client?: QueryClient;
}) {
  const [fallback] = React.useState(createQueryClient);
  return (
    <QueryClientProvider client={client ?? fallback}>
      {children}
      <Toaster theme="dark" position="bottom-right" closeButton richColors={false} />
    </QueryClientProvider>
  );
}
