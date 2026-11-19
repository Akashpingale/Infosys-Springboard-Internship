import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { REPORT_COPY } from '@/features/report/copy';
import { DownloadMenu } from '@/features/report/DownloadMenu';
import { renderWithApp } from '@/test/render';
import { REPORT, REPORT_URL, RUN_ID, readBlob } from '@/test/reportHandlers';
import { server } from '@/test/server';

const PDF_NAME = 'startup-validation_cropscan-ai-crop-disease-detection_2026-11-16.pdf';
const MD_NAME = 'startup-validation_cropscan-ai-crop-disease-detection_2026-11-16.md';
const JSON_NAME = 'startup-validation_cropscan-ai-crop-disease-detection_2026-11-16.json';

let saved: { name: string | null }[];
let blobs: Blob[];

beforeEach(() => {
  saved = [];
  blobs = [];
  Object.defineProperty(URL, 'createObjectURL', {
    writable: true,
    configurable: true,
    value: (blob: Blob) => {
      blobs.push(blob);
      return 'blob:stub';
    },
  });
  Object.defineProperty(URL, 'revokeObjectURL', { writable: true, configurable: true, value: () => undefined });
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (this: HTMLAnchorElement) {
    saved.push({ name: this.getAttribute('download') });
  });
});

afterEach(() => {
  vi.restoreAllMocks();
});

function file(body: string, type: string, name: string) {
  return new HttpResponse(body, { headers: { 'Content-Type': type, 'Content-Disposition': `attachment; filename="${name}"` } });
}

function open(pdfAvailable = true) {
  return renderWithApp(<DownloadMenu runId={RUN_ID} document={REPORT} pdfAvailable={pdfAvailable} />);
}

async function openMenu(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole('button', { name: REPORT_COPY.download }));
  return screen.getByRole('dialog', { name: 'Download this report' });
}

describe('Download menu', () => {
  it('offers PDF, Markdown and JSON', async () => {
    const user = userEvent.setup();
    open();

    await openMenu(user);

    for (const name of ['PDF', 'Markdown', 'JSON']) {
      expect(screen.getByRole('button', { name: new RegExp(`^${name}`) })).toBeEnabled();
    }
  });

  it('saves the PDF the backend rendered, under the name the backend gave it', async () => {
    const asked: string[] = [];
    server.use(
      http.get(`${REPORT_URL}/pdf`, ({ request }) => {
        asked.push(request.url);
        return file('%PDF-1.4 fake', 'application/pdf', PDF_NAME);
      }),
    );
    const user = userEvent.setup();
    open();

    await openMenu(user);
    await user.click(screen.getByRole('button', { name: /^PDF/ }));

    await waitFor(() => expect(saved).toEqual([{ name: PDF_NAME }]));
    expect(asked).toEqual([`${REPORT_URL}/pdf`]);
    expect(await readBlob(blobs[0]!)).toBe('%PDF-1.4 fake');
    expect(await screen.findByRole('status')).toHaveTextContent(`Saved as ${PDF_NAME}.`);
  });

  it('saves the Markdown the backend rendered', async () => {
    server.use(http.get(`${REPORT_URL}/markdown`, () => file('# Startup validation report\n', 'text/markdown', MD_NAME)));
    const user = userEvent.setup();
    open();

    await openMenu(user);
    await user.click(screen.getByRole('button', { name: /^Markdown/ }));

    await waitFor(() => expect(saved).toEqual([{ name: MD_NAME }]));
    expect(await readBlob(blobs[0]!)).toBe('# Startup validation report\n');
  });

  it('saves the stored report document as JSON without asking the server again', async () => {
    const user = userEvent.setup();
    open();

    await openMenu(user);
    await user.click(screen.getByRole('button', { name: /^JSON/ }));

    expect(saved).toEqual([{ name: JSON_NAME }]);
    expect(JSON.parse(await readBlob(blobs[0]!))).toEqual(REPORT);
  });

  it('keeps Markdown and JSON when the PDF fonts are not installed', async () => {
    const user = userEvent.setup();
    open(false);

    await openMenu(user);

    expect(screen.getByRole('button', { name: /^PDF/ })).toBeDisabled();
    expect(screen.getByText(REPORT_COPY.fontsMissing)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /^Markdown/ })).toBeEnabled();
    expect(screen.getByRole('button', { name: /^JSON/ })).toBeEnabled();
  });

  it("shows the backend's own words when the PDF cannot be made", async () => {
    server.use(
      http.get(`${REPORT_URL}/pdf`, () =>
        HttpResponse.json(
          {
            error: {
              code: 'report_render_failed',
              message: 'The report fonts are not installed. See the setup guide. Missing: IBMPlexSans-Regular.ttf.',
            },
          },
          { status: 500 },
        ),
      ),
    );
    const user = userEvent.setup();
    open();

    await openMenu(user);
    await user.click(screen.getByRole('button', { name: /^PDF/ }));

    expect(await screen.findByRole('alert')).toHaveTextContent('The report fonts are not installed. See the setup guide.');
    expect(saved).toEqual([]);
  });

  it('closes with Escape and gives focus back to the button', async () => {
    const user = userEvent.setup();
    open();

    await openMenu(user);
    await user.keyboard('{Escape}');

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    expect(screen.getByRole('button', { name: REPORT_COPY.download })).toHaveFocus();
  });
});
