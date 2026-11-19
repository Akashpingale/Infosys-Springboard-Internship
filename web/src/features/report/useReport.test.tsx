import { act, renderHook, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import type * as React from 'react';
import { describe, expect, it } from 'vitest';

import { Providers } from '@/app/providers';
import {
  canHaveReport,
  fileSlug,
  reportFileName,
  reportKey,
  useDeleteReport,
  useGenerateReport,
  useReport,
} from '@/features/report/useReport';
import { testQueryClient } from '@/test/render';
import { REPORT, REPORT_URL, RUN_ID, notFound, reportWith } from '@/test/reportHandlers';
import { CANCELLED, DONE, FAILED, PARTIAL, RUNNING } from '@/test/runFixtures';
import { server } from '@/test/server';

function wrapper(client = testQueryClient()) {
  return {
    client,
    wrapper: ({ children }: { children: React.ReactNode }) => <Providers client={client}>{children}</Providers>,
  };
}

describe('Report file names', () => {
  it.each([
    ['CropScan: AI crop disease detection', 'cropscan-ai-crop-disease-detection'],
    ['Caf\u00e9 Se\u00f1or \u00fcber', 'cafe-senor-uber'],
    ['a"; filename=evil.exe\r\nX-Header: 1', 'a-filename-evil-exe-x-header-1'],
    ['../../etc/passwd', 'etc-passwd'],
    ['', 'idea'],
    ['   ', 'idea'],
    ['\u0915\u0943\u0937\u093f \u{1f600}', 'idea'],
    ['word '.repeat(30), 'word-word-word-word-word-word-word-word'],
  ])('makes the same slug as the backend for %j', (title, slug) => {
    expect(fileSlug(title)).toBe(slug);
  });

  it('names each format after the idea and the report date', () => {
    expect(reportFileName(REPORT, 'json')).toBe('startup-validation_cropscan-ai-crop-disease-detection_2026-11-16.json');
    expect(reportFileName(REPORT, 'pdf')).toMatch(/\.pdf$/);
    expect(reportFileName(REPORT, 'markdown')).toMatch(/\.md$/);
    const undated = reportWith((document) => {
      document.meta.generated_at = 'soon';
    });
    expect(reportFileName(undated, 'json')).toMatch(/^startup-validation_cropscan-ai-crop-disease-detection_\d{4}-\d{2}-\d{2}\.json$/);
  });
});

describe('Which runs can have a report', () => {
  it('is a finished run with a complete or partial result', () => {
    expect(canHaveReport(DONE)).toBe(true);
    expect(canHaveReport(PARTIAL)).toBe(true);
    expect(canHaveReport(FAILED)).toBe(false);
    expect(canHaveReport(CANCELLED)).toBe(false);
    expect(canHaveReport(RUNNING)).toBe(false);
    expect(canHaveReport(undefined)).toBe(false);
    expect(canHaveReport({ ...DONE, result: { ...DONE.result!, status: 'failed' } })).toBe(false);
  });
});

describe('Report hooks', () => {
  it('reads the stored report, and a missing one as none rather than an error', async () => {
    server.use(http.get(REPORT_URL, () => HttpResponse.json(REPORT)));
    const first = wrapper();
    const found = renderHook(() => useReport(RUN_ID, true), { wrapper: first.wrapper });
    await waitFor(() => expect(found.result.current.data).toEqual(REPORT));

    server.use(http.get(REPORT_URL, () => notFound()));
    const second = wrapper();
    const missing = renderHook(() => useReport(RUN_ID, true), { wrapper: second.wrapper });
    await waitFor(() => expect(missing.result.current.isSuccess).toBe(true));
    expect(missing.result.current.data).toBeNull();
  });

  it('sends nothing while it is not enabled', () => {
    const { wrapper: Wrapper } = wrapper();
    const view = renderHook(() => useReport(RUN_ID, false), { wrapper: Wrapper });

    expect(view.result.current.fetchStatus).toBe('idle');
  });

  it('generates with the options asked for, then stores the answer as the report', async () => {
    const bodies: unknown[] = [];
    server.use(
      http.post(REPORT_URL, async ({ request }) => {
        bodies.push(await request.json());
        return HttpResponse.json(REPORT);
      }),
    );
    const { client, wrapper: Wrapper } = wrapper();
    const view = renderHook(() => useGenerateReport(RUN_ID), { wrapper: Wrapper });

    await act(async () => {
      await view.result.current.mutateAsync({ force: true, narrative: false });
    });

    expect(bodies).toEqual([{ force: true, narrative: false }]);
    expect(client.getQueryData(reportKey(RUN_ID))).toEqual(REPORT);
  });

  it('deletes the stored report', async () => {
    const asked: string[] = [];
    server.use(
      http.delete(REPORT_URL, ({ request }) => {
        asked.push(request.method);
        return new HttpResponse(null, { status: 204 });
      }),
    );
    const { client, wrapper: Wrapper } = wrapper();
    client.setQueryData(reportKey(RUN_ID), REPORT);
    const view = renderHook(() => ({ report: useReport(RUN_ID, false), remove: useDeleteReport(RUN_ID) }), {
      wrapper: Wrapper,
    });
    expect(view.result.current.report.data).toEqual(REPORT);

    await act(async () => {
      await view.result.current.remove.mutateAsync();
    });

    expect(asked).toEqual(['DELETE']);
    await waitFor(() => expect(view.result.current.report.data).toBeNull());
    expect(client.getQueryData(reportKey(RUN_ID))).toBeNull();
  });
});
