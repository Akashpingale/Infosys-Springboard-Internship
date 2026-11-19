import { screen, within } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';

import { API_URL } from '@/api/client';
import type { MetaResponse } from '@/api/queries';
import { StatusPage } from '@/features/status/StatusPage';
import { META } from '@/test/fixtures';
import { renderWithApp } from '@/test/render';
import { metaWith } from '@/test/reportHandlers';
import { server } from '@/test/server';

const HEALTH = { status: 'ok', llm_configured: true, search_configured: true };

function serve(meta: MetaResponse) {
  server.use(
    http.get(`${API_URL}/health`, () => HttpResponse.json(HEALTH)),
    http.get(`${API_URL}/api/meta`, () => HttpResponse.json(meta)),
  );
}

function value(region: HTMLElement, label: string): string | null {
  return within(region).getByText(label).closest('div')!.querySelector('dd')!.textContent;
}

describe('Status: the report and the profiles', () => {
  it('says the PDF fonts are installed, and which profiles are in use', async () => {
    serve(metaWith(true));
    renderWithApp(<StatusPage />);

    const region = await screen.findByRole('region', { name: 'Report and profiles' });
    expect(value(region, 'PDF fonts')).toBe('Installed');
    expect(value(region, 'Query profile')).toBe('v1');
    expect(value(region, 'Prompt profile')).toBe('v1');
    expect(value(region, 'Time limit for the written summary')).toBe('1:00');
    expect(within(region).queryByText(/setup guide/)).not.toBeInTheDocument();
  });

  it('says the PDF fonts are not installed and that the other formats still work', async () => {
    serve(metaWith(false));
    renderWithApp(<StatusPage />);

    const region = await screen.findByRole('region', { name: 'Report and profiles' });
    expect(value(region, 'PDF fonts')).toBe('Not installed');
    expect(within(region).getByText(/still be downloaded as Markdown and JSON/)).toBeInTheDocument();
    expect(region.textContent).not.toMatch(/assets|fonts[\\/]|\.ttf/);
  });

  it('leaves the panel out for a backend that does not report it', async () => {
    serve(META);
    renderWithApp(<StatusPage />);

    await screen.findByRole('region', { name: 'Limits' });
    expect(screen.queryByRole('region', { name: 'Report and profiles' })).not.toBeInTheDocument();
  });
});
