import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import type * as React from 'react';
import { Route, Routes, useLocation } from 'react-router-dom';
import { afterEach, describe, expect, it } from 'vitest';

import { API_URL } from '@/api/client';
import { REPORT_COPY } from '@/features/report/copy';
import { REPORT_BUTTON_LABELS, ReportButton, reportButtonState } from '@/features/report/ReportButton';
import { useGenerateReport } from '@/features/report/useReport';
import { ResultsHeader } from '@/features/results/ResultsHeader';
import type { RunDetail } from '@/features/run/useRun';
import { renderWithApp } from '@/test/render';
import { CURRENT, NONE, REPORT, REPORT_URL, runWith } from '@/test/reportHandlers';
import { CANCELLED, DONE, FAILED, PARTIAL, RUNNING } from '@/test/runFixtures';
import { server } from '@/test/server';

const releases: (() => void)[] = [];

afterEach(() => {
  for (const release of releases.splice(0)) {
    release();
  }
});

function Probe() {
  const location = useLocation();
  return <p>{`Report page ${JSON.stringify(location.state)}`}</p>;
}

function show(run: RunDetail, extra: React.ReactNode = null) {
  return renderWithApp(
    <Routes>
      <Route
        path="/runs/:runId"
        element={
          <>
            <ReportButton run={run} />
            {extra}
          </>
        }
      />
      <Route path="/runs/:runId/report" element={<Probe />} />
    </Routes>,
    { route: `/runs/${run.id}` },
  );
}

function Starter({ runId }: { runId: string }) {
  const generate = useGenerateReport(runId);
  return (
    <button type="button" onClick={() => generate.mutate({})}>
      start
    </button>
  );
}

describe('Results header: the report button', () => {
  it('reads "Generate report" before there is a report, and asks the report page to write one', async () => {
    const user = userEvent.setup();
    show(runWith(NONE));

    await user.click(screen.getByRole('button', { name: REPORT_COPY.generate }));

    expect(await screen.findByText('Report page {"generate":true}')).toBeInTheDocument();
  });

  it('reads "View report" for a current report and opens it without writing', async () => {
    const user = userEvent.setup();
    show(runWith(CURRENT));

    const link = screen.getByRole('link', { name: REPORT_COPY.view });
    expect(link).toHaveAttribute('href', `/runs/${DONE.id}/report`);
    await user.click(link);

    expect(await screen.findByText('Report page null')).toBeInTheDocument();
  });

  it('reads "Update report" for an out-of-date report', async () => {
    const user = userEvent.setup();
    show(runWith({ ...CURRENT, stale: true }));

    await user.click(screen.getByRole('button', { name: REPORT_COPY.update }));

    expect(await screen.findByText('Report page {"generate":true}')).toBeInTheDocument();
  });

  it('reads "Generating" and cannot be pressed while a report is being written', async () => {
    let release: () => void = () => undefined;
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    releases.push(release);
    server.use(
      http.post(REPORT_URL, async () => {
        await gate;
        return HttpResponse.json(REPORT);
      }),
      http.get(`${API_URL}/api/runs/${DONE.id}`, () => HttpResponse.json(runWith(CURRENT))),
    );
    const user = userEvent.setup();
    show(runWith(NONE), <Starter runId={DONE.id} />);

    await user.click(screen.getByRole('button', { name: 'start' }));

    const busy = await screen.findByRole('button', { name: REPORT_COPY.generatingButton });
    expect(busy).toBeDisabled();
    release();
    await waitFor(() => expect(screen.queryByRole('button', { name: REPORT_COPY.generatingButton })).not.toBeInTheDocument());
  });

  it('treats a run detail from an older backend, with no report block, as having no report', () => {
    show({ ...DONE, report: undefined });

    expect(screen.getByRole('button', { name: REPORT_COPY.generate })).toBeInTheDocument();
  });

  it('is offered for a partial run, and not for a run that failed, was cancelled or is still going', () => {
    expect(reportButtonState(runWith(NONE, PARTIAL), false)).toBe('generate');
    for (const run of [FAILED, CANCELLED, RUNNING]) {
      const { unmount } = show(runWith(NONE, run));
      expect(screen.queryByRole('button')).not.toBeInTheDocument();
      expect(screen.queryByRole('link')).not.toBeInTheDocument();
      unmount();
    }
  });

  it('uses the four labels of the copy table', () => {
    expect(Object.values(REPORT_BUTTON_LABELS)).toEqual(['Generate report', 'Generating', 'View report', 'Update report']);
  });

  it('sits with the other actions in the results header', () => {
    renderWithApp(
      <ResultsHeader run={runWith(CURRENT)} active="overview" onChange={() => undefined} actions={<button type="button">Delete</button>} />,
    );

    const actions = screen.getByRole('button', { name: 'Delete' }).parentElement as HTMLElement;
    expect(within(actions).getByRole('link', { name: REPORT_COPY.view })).toBeInTheDocument();
    expect(actions).toHaveAttribute('data-print-hide');
  });
});
