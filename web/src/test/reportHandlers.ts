import { http, HttpResponse } from 'msw';
import { vi } from 'vitest';

import { API_URL } from '@/api/client';
import type { MetaResponse } from '@/api/queries';
import type { ReportDocument, ReportStatus } from '@/features/report/useReport';
import type { RunDetail } from '@/features/run/useRun';
import { META } from '@/test/fixtures';
import fixture from '@/test/reportFixture.synthetic.json';
import { DONE } from '@/test/runFixtures';
import { server } from '@/test/server';

export const REPORT = fixture as unknown as ReportDocument;
export const RUN_ID = DONE.id;
export const REPORT_URL = `${API_URL}/api/runs/${RUN_ID}/report`;

export const CURRENT: ReportStatus = {
  exists: true,
  generated_at: REPORT.meta.generated_at,
  stale: false,
  narrative_status: 'ok',
};
export const NONE: ReportStatus = { exists: false, generated_at: null, stale: false, narrative_status: null };

export function metaWith(pdfAvailable = true): MetaResponse {
  return {
    ...META,
    report: { available: true, pdf_available: pdfAvailable, time_limit_s: 60 },
    profiles: { query_profile: 'v1', prompt_profile: 'v1', app_version: '0.1.0' },
  };
}

export function reportWith(change: (document: ReportDocument) => void): ReportDocument {
  const copy = structuredClone(REPORT);
  change(copy);
  return copy;
}

export function runWith(report: ReportStatus | null, base: RunDetail = DONE): RunDetail {
  return { ...base, report };
}

export function notFound() {
  return HttpResponse.json({ error: { code: 'report_not_found', message: 'Generate the report first.' } }, { status: 404 });
}

export interface ServeOptions {
  run?: RunDetail;
  report?: ReportDocument | null;
  meta?: MetaResponse;
}

export interface AbortRecord {
  aborted: string[];
}

export function abortableFetch(): AbortRecord {
  const record: AbortRecord = { aborted: [] };
  const real = globalThis.fetch;
  vi.stubGlobal('fetch', (input: RequestInfo | URL, init: RequestInit = {}) => {
    const { signal, ...rest } = init;
    if (!signal) {
      return real(input, init);
    }
    return new Promise<Response>((resolve, reject) => {
      const stop = () => {
        record.aborted.push(String(input));
        reject(new DOMException('The request was aborted.', 'AbortError'));
      };
      if (signal.aborted) {
        stop();
        return;
      }
      signal.addEventListener('abort', stop);
      real(input, rest).then(resolve, reject);
    });
  });
  return record;
}

export function readBlob(blob: Blob): Promise<string> {
  if (typeof blob.text === 'function') {
    return blob.text();
  }
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(reader.error);
    reader.readAsText(blob);
  });
}

export function serveReport({ run = runWith(CURRENT), report = REPORT, meta = metaWith() }: ServeOptions = {}) {
  server.use(
    http.get(`${API_URL}/api/runs/${run.id}`, () => HttpResponse.json(run)),
    http.get(`${API_URL}/api/meta`, () => HttpResponse.json(meta)),
    http.get(`${API_URL}/api/runs/${run.id}/report`, () => (report ? HttpResponse.json(report) : notFound())),
  );
}
