import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { API_URL } from '@/api/client';
import { REPORT_COPY } from '@/features/report/copy';
import { ReportPage } from '@/features/report/ReportPage';
import type { ReportDocument } from '@/features/report/useReport';
import { MESSAGES } from '@/lib/format';
import { renderWithApp } from '@/test/render';
import {
  CURRENT,
  NONE,
  abortableFetch,
  type AbortRecord,
  REPORT,
  REPORT_URL,
  RUN_ID,
  metaWith,
  notFound,
  reportWith,
  runWith,
  serveReport,
} from '@/test/reportHandlers';
import { FAILED, PARTIAL, RUNNING } from '@/test/runFixtures';
import { server } from '@/test/server';

const ROUTE = `/runs/${RUN_ID}/report`;
const TITLES = [...(REPORT.sections ?? []), ...(REPORT.appendix_sections ?? [])]
  .filter((section) => section.id !== 'cover')
  .map((section) => section.title);

const gates: (() => void)[] = [];
let aborts: AbortRecord;

beforeEach(() => {
  aborts = abortableFetch();
});

afterEach(() => {
  vi.unstubAllGlobals();
  for (const release of gates.splice(0)) {
    release();
  }
  vi.restoreAllMocks();
});

function show(state?: unknown) {
  return renderWithApp(
    <Routes>
      <Route path="/runs/:runId/report" element={<ReportPage />} />
      <Route path="/runs/:runId" element={<p>Results workspace</p>} />
    </Routes>,
    { route: ROUTE, ...(state === undefined ? {} : { state }) },
  );
}

function posts(reply: () => Response | Promise<Response> = () => HttpResponse.json(REPORT)) {
  const bodies: unknown[] = [];
  server.use(
    http.post(REPORT_URL, async ({ request }) => {
      bodies.push(await request.json());
      return reply();
    }),
  );
  return bodies;
}

function held(document: ReportDocument = REPORT) {
  let release: () => void = () => undefined;
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  gates.push(release);
  const bodies = posts(async () => {
    await gate;
    return HttpResponse.json(document);
  });
  return { bodies, release: () => release() };
}

function narrow(matches: boolean) {
  vi.spyOn(window, 'matchMedia').mockImplementation((query: string) => ({
    matches,
    media: query,
    onchange: null,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
    addListener: () => undefined,
    removeListener: () => undefined,
    dispatchEvent: () => false,
  }));
}

describe('Report page: reading', () => {
  it('shows the title block, the version and limits lines, and every section in catalogue order', async () => {
    serveReport();
    show();

    await screen.findByRole('article');
    const title = screen.getByRole('heading', { level: 1, name: REPORT.meta.idea_title });
    const header = title.closest('[data-report-header]') as HTMLElement;
    expect(within(header).getByText(REPORT.title)).toBeInTheDocument();
    expect(within(header).getByText('Complete')).toBeInTheDocument();
    expect(within(header).getByText(REPORT.meta.industry)).toBeInTheDocument();
    expect(within(header).getByText(/^Generated /)).toBeInTheDocument();
    expect(within(header).getByText('Version 0.1.0, report format 1, summary prompt report-v1')).toBeInTheDocument();
    expect(within(header).getByText(REPORT_COPY.limits)).toBeInTheDocument();
    const article = screen.getByRole('article');
    expect(title).toHaveTextContent(REPORT.subtitle);
    expect(within(article).getAllByRole('heading', { level: 2 }).map((heading) => heading.textContent)).toEqual(TITLES);
  });

  it('lists every section in the table of contents and marks the one chosen', async () => {
    serveReport();
    const user = userEvent.setup();
    show();

    const contents = await screen.findByRole('navigation', { name: 'Contents' });
    const links = within(contents).getAllByRole('link');
    expect(links.map((link) => link.textContent)).toEqual(TITLES);
    expect(within(contents).queryByRole('button')).not.toBeInTheDocument();

    await user.click(within(contents).getByRole('link', { name: 'Risk assessment' }));

    expect(within(contents).getByRole('link', { name: 'Risk assessment' })).toHaveAttribute('aria-current', 'location');
    expect(document.activeElement).toBe(document.getElementById('report-risks'));
  });

  it('turns the contents into one collapsible list below 1024 px', async () => {
    narrow(true);
    serveReport();
    const user = userEvent.setup();
    show();

    const contents = await screen.findByRole('navigation', { name: 'Contents' });
    const toggle = within(contents).getByRole('button', { name: 'Contents' });
    expect(screen.getAllByRole('navigation', { name: 'Contents' })).toHaveLength(1);
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
    expect(within(contents).queryByRole('link')).not.toBeInTheDocument();

    await user.click(toggle);

    expect(toggle).toHaveAttribute('aria-expanded', 'true');
    expect(within(contents).getAllByRole('link')).toHaveLength(TITLES.length);
    await user.click(within(contents).getByRole('link', { name: 'Sources' }));
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
    expect(document.activeElement).toBe(document.getElementById('report-sources'));
  });

  it('jumps from a citation number to its numbered source', async () => {
    serveReport();
    const user = userEvent.setup();
    show();

    const summary = await screen.findByRole('region', { name: 'Executive summary' });
    const cite = within(summary).getAllByRole('link', { name: 'Source [1]' })[0]!;
    expect(cite).toHaveAttribute('href', '#report-source-1');

    await user.click(cite);

    const entry = document.getElementById('report-source-1')!;
    expect(document.activeElement).toBe(entry);
    expect(entry).toHaveTextContent(REPORT.bibliography![0]!.title);
  });

  it('lists the sources with links that open in a new tab', async () => {
    serveReport();
    show();

    const sources = await screen.findByRole('list', { name: 'Numbered sources' });
    const items = within(sources).getAllByRole('listitem');
    expect(items).toHaveLength(REPORT.bibliography!.length);
    const first = REPORT.bibliography![0]!;
    const link = within(items[0]!).getByRole('link');
    expect(link).toHaveAttribute('href', first.url);
    expect(link).toHaveAttribute('target', '_blank');
    expect(link).toHaveAttribute('rel', 'noopener noreferrer');
  });

  it('goes back to the results', async () => {
    serveReport();
    const user = userEvent.setup();
    show();

    await screen.findByRole('article');
    await user.click(screen.getByRole('link', { name: REPORT_COPY.back }));

    expect(await screen.findByText('Results workspace')).toBeInTheDocument();
  });
});

describe('Report page: banners', () => {
  it('says an out-of-date report is out of date and regenerates it', async () => {
    serveReport({ run: runWith({ ...CURRENT, stale: true }) });
    const bodies = posts();
    const user = userEvent.setup();
    show();

    const banner = (await screen.findByText(REPORT_COPY.stale)).closest('[role="status"]') as HTMLElement;
    await user.click(within(banner).getByRole('button', { name: REPORT_COPY.regenerate }));

    await waitFor(() => expect(bodies).toEqual([{ force: true, narrative: true }]));
    await waitFor(() => expect(screen.queryByText(REPORT_COPY.stale)).not.toBeInTheDocument());
  });

  it('offers to try the written summary again when it failed', async () => {
    const failed = reportWith((document) => {
      document.meta.narrative_status = 'failed';
    });
    serveReport({ run: runWith({ ...CURRENT, narrative_status: 'failed' }), report: failed });
    const bodies = posts();
    const user = userEvent.setup();
    show();

    const banner = (await screen.findByText(REPORT_COPY.narrativeFailed)).closest('[role="status"]') as HTMLElement;
    await user.click(within(banner).getByRole('button', { name: REPORT_COPY.tryAgain }));

    await waitFor(() => expect(bodies).toEqual([{ force: true, narrative: true }]));
  });

  it('names the parts of a partial validation that did not finish', async () => {
    const partial = reportWith((document) => {
      document.meta.run_status = 'partial';
    });
    serveReport({ run: runWith(CURRENT, PARTIAL), report: partial });
    show();

    expect(await screen.findByText('Some parts of this validation did not finish: Comparing competitors.')).toBeInTheDocument();
    const header = screen.getByRole('heading', { level: 1 }).closest('[data-report-header]') as HTMLElement;
    expect(within(header).getByText('Partial')).toBeInTheDocument();
  });

  it('shows no banner for a current, complete report with its summary', async () => {
    serveReport();
    show();

    await screen.findByRole('article');
    expect(screen.queryByText(REPORT_COPY.stale)).not.toBeInTheDocument();
    expect(screen.queryByText(REPORT_COPY.narrativeFailed)).not.toBeInTheDocument();
    expect(screen.queryByText(/did not finish/)).not.toBeInTheDocument();
  });
});

describe('Report page: generating', () => {
  it('offers to generate when there is no report, says it is writing, then shows it', async () => {
    serveReport({ run: runWith(NONE), report: null });
    const { bodies, release } = held();
    const user = userEvent.setup();
    show();

    expect(await screen.findByText(REPORT_COPY.notGenerated)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: REPORT_COPY.generate }));

    const status = await screen.findByText(REPORT_COPY.generating);
    expect(status).toHaveAttribute('role', 'status');
    expect(status).toHaveAttribute('aria-live', 'polite');
    release();

    expect(await screen.findByRole('article')).toBeInTheDocument();
    expect(screen.queryByText(REPORT_COPY.generating)).not.toBeInTheDocument();
    expect(bodies).toEqual([{ force: false, narrative: true }]);
  });

  it('cancels a report being written by aborting the request', async () => {
    serveReport({ run: runWith(NONE), report: null });
    held();
    const user = userEvent.setup();
    show();

    await user.click(await screen.findByRole('button', { name: REPORT_COPY.generate }));
    await screen.findByText(REPORT_COPY.generating);
    await user.click(screen.getByRole('button', { name: REPORT_COPY.cancel }));

    await waitFor(() => expect(screen.queryByText(REPORT_COPY.generating)).not.toBeInTheDocument());
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    expect(screen.getByText(REPORT_COPY.notGenerated)).toBeInTheDocument();
    expect(aborts.aborted).toEqual([REPORT_URL]);
  });

  it('starts writing straight away when the results header asked for a report', async () => {
    serveReport({ run: runWith(NONE), report: null });
    const bodies = posts();
    show({ generate: true });

    expect(await screen.findByRole('article')).toBeInTheDocument();
    expect(bodies).toEqual([{ force: false, narrative: true }]);
  });

  it('asks before replacing a written summary, and does nothing when kept', async () => {
    serveReport();
    const bodies = posts();
    const user = userEvent.setup();
    show();

    await screen.findByRole('article');
    const header = screen.getByRole('heading', { level: 1 }).closest('[data-report-header]') as HTMLElement;
    await user.click(within(header).getByRole('button', { name: REPORT_COPY.regenerate }));
    let dialog = await screen.findByRole('dialog');
    expect(within(dialog).getByRole('heading', { name: REPORT_COPY.confirmTitle })).toBeInTheDocument();
    await user.click(within(dialog).getByRole('button', { name: 'Keep it' }));
    expect(bodies).toEqual([]);

    await user.click(within(header).getByRole('button', { name: REPORT_COPY.regenerate }));
    dialog = await screen.findByRole('dialog');
    await user.click(within(dialog).getByRole('button', { name: REPORT_COPY.regenerate }));

    await waitFor(() => expect(bodies).toEqual([{ force: true, narrative: true }]));
  });

  it('says plainly when the AI service could not be reached while writing', async () => {
    serveReport({ run: runWith(NONE), report: null });
    posts(() =>
      HttpResponse.json(
        { error: { code: 'llm_api_error', message: 'The AI service is not responding. Please try again.' } },
        { status: 502 },
      ),
    );
    const user = userEvent.setup();
    show();

    await user.click(await screen.findByRole('button', { name: REPORT_COPY.generate }));

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('The report was not written');
    expect(alert).toHaveTextContent('The AI service is not responding. Please try again.');
    expect(within(alert).getByRole('button', { name: REPORT_COPY.tryAgain })).toBeInTheDocument();
  });

  it('says the server cannot be reached when it is offline', async () => {
    serveReport({ run: runWith(NONE), report: null });
    posts(() => HttpResponse.error());
    const user = userEvent.setup();
    show();

    await user.click(await screen.findByRole('button', { name: REPORT_COPY.generate }));

    expect(await screen.findByRole('alert')).toHaveTextContent(MESSAGES.backendDown);
  });
});

describe('Report page: runs without a report', () => {
  it.each([
    ['still running', RUNNING],
    ['failed', FAILED],
  ])('explains that a run that is %s cannot have a report yet', async (_, run) => {
    server.use(
      http.get(`${API_URL}/api/runs/${run.id}`, () => HttpResponse.json(runWith(null, run))),
      http.get(`${API_URL}/api/meta`, () => HttpResponse.json(metaWith())),
    );
    show();

    expect(await screen.findByText(REPORT_COPY.notFinished)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: REPORT_COPY.back })).toHaveAttribute('href', `/runs/${RUN_ID}`);
  });

  it('says the validation is not here when the run does not exist', async () => {
    server.use(
      http.get(`${API_URL}/api/runs/${RUN_ID}`, () =>
        HttpResponse.json({ error: { code: 'run_not_found', message: 'This validation could not be found.' } }, { status: 404 }),
      ),
      http.get(`${API_URL}/api/meta`, () => HttpResponse.json(metaWith())),
    );
    show();

    expect(await screen.findByRole('heading', { name: 'That validation is not here' })).toBeInTheDocument();
  });
});

describe('Report page: untrusted text', () => {
  it('renders markup in the report as plain text and links only web addresses', async () => {
    const hostile = '<img src=x onerror="alert(1)"><script>alert(2)</script>';
    const hostileReport = reportWith((report) => {
      const summary = report.sections!.find((section) => section.id === 'executive_summary')!;
      summary.blocks = [{ type: 'paragraph', text: hostile, basis: 'ai_interpretation', cites: [1], narrative: true }];
      report.bibliography![0] = { ...report.bibliography![0]!, title: hostile, url: 'javascript:alert(3)' };
    });
    serveReport({ report: hostileReport, run: runWith(CURRENT) });
    const { container } = show();

    await screen.findByRole('article');
    expect(screen.getAllByText(hostile).length).toBeGreaterThanOrEqual(2);
    expect(container.querySelector('img, script')).toBeNull();
    expect(container.querySelector('a[href^="javascript"]')).toBeNull();
    expect(screen.getByText('javascript:alert(3)')).toBeInTheDocument();
  });
});

describe('Report page: missing report', () => {
  it('treats a report the server cannot find as not generated yet', async () => {
    server.use(
      http.get(`${API_URL}/api/runs/${RUN_ID}`, () => HttpResponse.json(runWith(NONE))),
      http.get(`${API_URL}/api/meta`, () => HttpResponse.json(metaWith())),
      http.get(REPORT_URL, () => notFound()),
    );
    show();

    expect(await screen.findByText(REPORT_COPY.notGenerated)).toBeInTheDocument();
  });
});
