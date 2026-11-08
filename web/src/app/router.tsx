/**
 * Routes (KIRO_UI_UPGRADE_SPEC.md Section 5, and Prompt J).
 *
 * Each screen is loaded on its own. The form, the results workspace, the history and the status
 * page share very little: the results workspace alone carries the five tabs, the comparison matrix
 * and the charts, and a founder opening the form has no use for any of it yet. Splitting here keeps
 * the first load to the shell plus the form.
 *
 * `React.lazy` wants a default export and these modules export their component by name, so each
 * import maps the named export onto `default`. The waiting state is in AppShell, around the outlet,
 * so the header and the navigation stay put while a screen arrives.
 */

import * as React from 'react';
import { Route, Routes } from 'react-router-dom';

import { AppShell } from '@/app/AppShell';

const NewValidationPage = React.lazy(() =>
  import('@/features/new-validation/NewValidationPage').then((module) => ({
    default: module.NewValidationPage,
  })),
);

const RunPage = React.lazy(() =>
  import('@/features/run/RunPage').then((module) => ({ default: module.RunPage })),
);

const HistoryPage = React.lazy(() =>
  import('@/features/history/HistoryPage').then((module) => ({ default: module.HistoryPage })),
);

const StatusPage = React.lazy(() =>
  import('@/features/status/StatusPage').then((module) => ({ default: module.StatusPage })),
);

const NotFoundPage = React.lazy(() =>
  import('@/features/not-found/NotFoundPage').then((module) => ({ default: module.NotFoundPage })),
);

// Development only, and lazy as well, so the production bundle does not carry it at all.
const DesignPage = React.lazy(() =>
  import('@/features/design/DesignPage').then((module) => ({ default: module.DesignPage })),
);

export function AppRoutes() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<NewValidationPage />} />
        <Route path="runs/:runId" element={<RunPage />} />
        <Route path="history" element={<HistoryPage />} />
        <Route path="status" element={<StatusPage />} />
        {import.meta.env.DEV ? <Route path="design" element={<DesignPage />} /> : null}
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}
