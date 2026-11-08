/**
 * The export menu (KIRO_UI_UPGRADE_SPEC.md Prompt I, Section 7.4).
 *
 * MSW answers the report endpoint, so no run is read from a real server. Saving a file and printing
 * are browser jobs jsdom does not do, so both are stubbed and the call itself is checked: that the
 * Markdown comes from the backend rather than being written here, and that PDF goes through the
 * page's print path rather than printing one tab.
 */

import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { API_URL } from '@/api/client';
import { ExportMenu, PDF_HINT } from '@/features/results/ExportMenu';
import type { RunDetail } from '@/features/run/useRun';
import type { PipelineResult } from '@/lib/results';
import fintech from '@/test/liveFintech.json';
import { renderWithApp } from '@/test/render';
import { server } from '@/test/server';

const LIVE = fintech as unknown as RunDetail;
const RESULT = LIVE.result!;
const REPORT_URL = `${API_URL}/api/runs/${LIVE.id}/report.md`;

let saved: { name: string | null }[];

beforeEach(() => {
  saved = [];
  Object.defineProperty(URL, 'createObjectURL', {
    writable: true,
    configurable: true,
    value: () => 'blob:stub',
  });
  Object.defineProperty(URL, 'revokeObjectURL', { writable: true, configurable: true, value: () => undefined });
  // The download attribute is what names the file, so the anchor is watched rather than the blob.
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (this: HTMLAnchorElement) {
    saved.push({ name: this.getAttribute('download') });
  });
});

afterEach(() => {
  vi.restoreAllMocks();
});

function open(result: PipelineResult | null = RESULT, onPrint = vi.fn()) {
  const view = renderWithApp(<ExportMenu run={LIVE} result={result} onPrint={onPrint} />);
  return { ...view, onPrint };
}

async function openMenu(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole('button', { name: /export/i }));
  return screen.getByText('Markdown report').closest('[role="dialog"], div') as HTMLElement;
}

describe('Export menu', () => {
  it('offers Markdown, JSON and PDF, and says what each one is', async () => {
    const user = userEvent.setup();
    open();

    await openMenu(user);

    expect(screen.getByText('Markdown report')).toBeInTheDocument();
    expect(screen.getByText(/the full written report from the server/i)).toBeInTheDocument();
    expect(screen.getByText('JSON result')).toBeInTheDocument();
    expect(screen.getByText(/exactly what the backend returned/i)).toBeInTheDocument();
    expect(screen.getByText('PDF')).toBeInTheDocument();
    expect(screen.getByText(PDF_HINT)).toBeInTheDocument();
  });

  it('takes the Markdown from the backend report endpoint, not from this page', async () => {
    let asked = 0;
    server.use(
      http.get(REPORT_URL, () => {
        asked += 1;
        return HttpResponse.text('# Validation report\n\nWritten by the backend.');
      }),
    );
    const user = userEvent.setup();
    open();

    await openMenu(user);
    await user.click(screen.getByText('Markdown report'));

    await waitFor(() => expect(asked).toBe(1));
    expect(saved).toHaveLength(1);
    expect(saved[0]?.name).toMatch(/^validation-cash-flow-and-expense.*-2026-10-27\.md$/);
    expect(await screen.findByRole('status')).toHaveTextContent(/saved as validation-.*\.md/i);
  });

  it("shows the backend's own words when there is no report yet", async () => {
    server.use(
      http.get(REPORT_URL, () =>
        HttpResponse.json(
          { error: { code: 'report_not_ready', message: 'This validation produced no report.' } },
          { status: 409 },
        ),
      ),
    );
    const user = userEvent.setup();
    open();

    await openMenu(user);
    await user.click(screen.getByText('Markdown report'));

    expect(await screen.findByRole('alert')).toHaveTextContent('This validation produced no report.');
    expect(saved).toHaveLength(0);
  });

  it('says the server is not running when it cannot be reached', async () => {
    server.use(http.get(REPORT_URL, () => HttpResponse.error()));
    const user = userEvent.setup();
    open();

    await openMenu(user);
    await user.click(screen.getByText('Markdown report'));

    expect(await screen.findByRole('alert')).toHaveTextContent(/can\u2019t reach the server/i);
  });

  it('saves the result as JSON exactly as the backend returned it', async () => {
    const user = userEvent.setup();
    open();

    await openMenu(user);
    await user.click(screen.getByText('JSON result'));

    expect(saved).toHaveLength(1);
    expect(saved[0]?.name).toMatch(/\.json$/);
    expect(await screen.findByRole('status')).toHaveTextContent(/saved as validation-.*\.json/i);
  });

  it('offers no JSON for a run that produced nothing', async () => {
    const user = userEvent.setup();
    open(null);

    const menu = await openMenu(user);

    expect(within(menu).getByText('JSON result').closest('button')).toBeDisabled();
    expect(within(menu).getByText(/there is no result to save/i)).toBeInTheDocument();
  });

  it('asks the page to lay every section out before printing, and closes', async () => {
    const user = userEvent.setup();
    const { onPrint } = open();

    await openMenu(user);
    await user.click(screen.getByText('PDF'));

    expect(onPrint).toHaveBeenCalledTimes(1);
    await waitFor(() => expect(screen.queryByText('Markdown report')).not.toBeInTheDocument());
  });

  it('forgets the last message when the menu is closed again', async () => {
    const user = userEvent.setup();
    open();

    await openMenu(user);
    await user.click(screen.getByText('JSON result'));
    await screen.findByRole('status');

    await user.keyboard('{Escape}');
    await openMenu(user);

    expect(screen.queryByRole('status')).not.toBeInTheDocument();
  });
});
