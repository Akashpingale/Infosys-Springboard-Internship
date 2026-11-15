import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { API_URL } from '@/api/client';
import { ADVISOR_COPY } from '@/features/advisor/AdvisorTab';
import { NewValidationPage } from '@/features/new-validation/NewValidationPage';
import { RunPage } from '@/features/run/RunPage';
import type { RunDetail } from '@/features/run/useRun';
import { MVP_COPY } from '@/features/strategy/MvpSection';
import { EXTRACTED } from '@/test/fixtures';
import { renderWithApp } from '@/test/render';
import { DONE } from '@/test/runFixtures';
import { server } from '@/test/server';
import {
  EMPTY_THREAD,
  STRATEGY_DONE,
  STRATEGY_RUNNING,
  SYNTHETIC_STRATEGY_RESULT,
  metaWithStrategy,
  runUrl,
} from '@/test/strategyHandlers';

const PRINTED_WITH_STRATEGY = ['Overview', 'Market', 'Competitors', 'Strategy', 'Sources', 'Run details'];
const PRINTED_WITHOUT_STRATEGY = ['Overview', 'Market', 'Competitors', 'Sources', 'Run details'];
const STRATEGY_HEADINGS = ['SWOT', 'Risks', 'MVP plan', 'Go-to-market'];
const RISKS = SYNTHETIC_STRATEGY_RESULT.swot?.risks ?? [];
const FEATURES = SYNTHETIC_STRATEGY_RESULT.mvp?.features ?? [];

interface Printed {
  sections: string[];
  strategyHeadings: (string | null)[];
  text: string;
  rankingOpen: boolean | null;
  foldedToggles: number;
}

function show(run: RunDetail) {
  return http.get(runUrl(run.id), () => HttpResponse.json(run));
}

function countChatReads(counter: { reads: number }) {
  return http.get(`${runUrl()}/chat`, () => {
    counter.reads += 1;
    return HttpResponse.json(EMPTY_THREAD);
  });
}

function open() {
  return renderWithApp(
    <Routes>
      <Route path="/runs/:runId" element={<RunPage />} />
    </Routes>,
    { route: '/runs/run-123' },
  );
}

function capturePrint(onPrint?: () => void): Printed[] {
  const printed: Printed[] = [];
  Object.defineProperty(window, 'print', {
    writable: true,
    configurable: true,
    value: () => {
      onPrint?.();
      const layout = document.querySelector('section[aria-label="Overview"]')?.parentElement;
      const ranking = [...document.querySelectorAll('details')].find((node) =>
        node.querySelector('summary')?.textContent?.includes(MVP_COPY.ranking),
      );
      printed.push({
        sections: [...(layout?.children ?? [])].map((node) => node.getAttribute('aria-label') ?? ''),
        strategyHeadings: ['swot', 'risks', 'mvp', 'gtm'].map(
          (part) => document.getElementById(`strategy-${part}-heading`)?.textContent ?? null,
        ),
        text: document.body.textContent ?? '',
        rankingOpen: ranking ? ranking.open : null,
        foldedToggles: document.querySelectorAll('button[aria-expanded="false"][aria-controls]').length,
      });
    },
  });
  return printed;
}

async function printPage(user: ReturnType<typeof userEvent.setup>): Promise<void> {
  await user.click(await screen.findByRole('button', { name: /export/i }));
  await user.click(screen.getByText('PDF'));
}

function readBlob(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(reader.error);
    reader.readAsText(blob);
  });
}

describe('Printing: Strategy is laid out, the Advisor is not', () => {
  it('prints every Strategy section with its folded panels open, and no Advisor', async () => {
    const chat = { reads: 0 };
    server.use(show(STRATEGY_DONE), metaWithStrategy(), countChatReads(chat));
    const printed = capturePrint();
    const user = userEvent.setup();
    open();

    await printPage(user);

    await waitFor(() => expect(printed).toHaveLength(1));
    const page = printed[0]!;
    expect(page.sections).toEqual(PRINTED_WITH_STRATEGY);
    expect(page.strategyHeadings).toEqual(STRATEGY_HEADINGS);
    expect(page.text).toContain(SYNTHETIC_STRATEGY_RESULT.swot!.summary);
    expect(FEATURES).toHaveLength(8);
    for (const feature of FEATURES) {
      expect(page.text).toContain(feature.name);
    }
    expect(page.text).toContain(SYNTHETIC_STRATEGY_RESULT.gtm!.positioning.statement);
    expect(RISKS).toHaveLength(6);
    for (const risk of RISKS) {
      expect(page.text).toContain(risk.description);
      expect(page.text).toContain(risk.early_warning_signal);
    }
    expect(page.rankingOpen).toBe(true);
    expect(page.foldedToggles).toBe(0);
    expect(page.text).not.toContain(ADVISOR_COPY.title);
    expect(page.text).not.toContain(ADVISOR_COPY.empty);
    expect(chat.reads).toBe(0);
  });

  it('puts the page back afterwards: one tab, panels folded, risk details hidden again', async () => {
    server.use(show(STRATEGY_DONE), metaWithStrategy());
    const printed = capturePrint();
    const user = userEvent.setup();
    open();

    await user.click(await screen.findByRole('tab', { name: 'Strategy' }));
    await screen.findByRole('heading', { name: 'Risks' });
    await printPage(user);

    await waitFor(() => expect(printed).toHaveLength(1));
    await waitFor(() => expect(screen.getByRole('tabpanel')).toBeInTheDocument());
    expect(screen.getByRole('tab', { name: 'Strategy' })).toHaveAttribute('aria-selected', 'true');
    expect(document.querySelectorAll('details[open]')).toHaveLength(0);
    for (const risk of RISKS) {
      expect(screen.queryByText(risk.description)).not.toBeInTheDocument();
    }
    for (const toggle of screen.getAllByRole('button', { name: /^Show details/ })) {
      expect(toggle).toHaveAttribute('aria-expanded', 'false');
    }
  });

  it('prints the Advisor nowhere even when it was the open tab', async () => {
    const chat = { reads: 0 };
    server.use(show(STRATEGY_DONE), metaWithStrategy(), countChatReads(chat));
    let readsAtPrint = -1;
    const printed = capturePrint(() => {
      readsAtPrint = chat.reads;
    });
    const user = userEvent.setup();
    open();

    await user.click(await screen.findByRole('tab', { name: 'Advisor' }));
    await screen.findByText(ADVISOR_COPY.empty);
    const readsBefore = chat.reads;
    await printPage(user);

    await waitFor(() => expect(printed).toHaveLength(1));
    expect(printed[0]!.sections).toEqual(PRINTED_WITH_STRATEGY);
    expect(printed[0]!.text).not.toContain(ADVISOR_COPY.title);
    expect(printed[0]!.text).not.toContain(ADVISOR_COPY.empty);
    expect(readsAtPrint).toBe(readsBefore);
  });

  it('leaves Strategy out of a run that has none, rather than printing the offer and its form', async () => {
    server.use(show(DONE));
    const printed = capturePrint();
    const user = userEvent.setup();
    open();

    await printPage(user);

    await waitFor(() => expect(printed).toHaveLength(1));
    expect(printed[0]!.sections).toEqual(PRINTED_WITHOUT_STRATEGY);
    expect(printed[0]!.strategyHeadings).toEqual([null, null, null, null]);
    expect(printed[0]!.text).not.toContain('No strategy yet.');
    expect(printed[0]!.text).not.toContain('Resources and goals (optional)');
  });
});

describe('Export: Markdown and JSON with a strategy', () => {
  let blobs: Blob[];
  let names: (string | null)[];

  beforeEach(() => {
    blobs = [];
    names = [];
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
      names.push(this.getAttribute('download'));
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it.each([
    ['without', DONE],
    ['with', STRATEGY_DONE],
  ])('asks for the same Markdown report %s a strategy, once, and saves what the backend sent', async (_, run) => {
    const asked: { method: string; url: string; body: string }[] = [];
    const REPORT = `# Validation report\n\nWritten by the backend for ${run.id}.\n`;
    server.use(
      show(run),
      metaWithStrategy(),
      http.get(`${API_URL}/api/runs/${run.id}/report.md`, async ({ request }) => {
        asked.push({ method: request.method, url: request.url, body: await request.text() });
        return HttpResponse.text(REPORT);
      }),
    );
    const user = userEvent.setup();
    open();

    await user.click(await screen.findByRole('button', { name: /export/i }));
    await user.click(screen.getByText('Markdown report'));

    await waitFor(() => expect(names).toHaveLength(1));
    expect(asked).toEqual([{ method: 'GET', url: `${API_URL}/api/runs/run-123/report.md`, body: '' }]);
    expect(names[0]).toMatch(/\.md$/);
    expect(blobs[0]?.type).toBe('text/markdown;charset=utf-8');
    expect(await readBlob(blobs[0]!)).toBe(REPORT);
  });

  it('saves the JSON with the strategy fields, exactly as the backend returned it', async () => {
    server.use(show(STRATEGY_DONE), metaWithStrategy());
    const user = userEvent.setup();
    open();

    await user.click(await screen.findByRole('button', { name: /export/i }));
    await user.click(screen.getByText('JSON result'));

    await waitFor(() => expect(names).toHaveLength(1));
    expect(names[0]).toMatch(/\.json$/);
    const saved = JSON.parse(await readBlob(blobs[0]!)) as Record<string, unknown>;
    expect(saved).toEqual(STRATEGY_DONE.result);
    expect(saved.swot).toEqual(SYNTHETIC_STRATEGY_RESULT.swot);
    expect(saved.mvp).toEqual(SYNTHETIC_STRATEGY_RESULT.mvp);
    expect(saved.gtm).toEqual(SYNTHETIC_STRATEGY_RESULT.gtm);
    expect(saved.constraints).toEqual(SYNTHETIC_STRATEGY_RESULT.constraints);
  });
});

describe('Edit and re-run with constraints, end to end', () => {
  it('carries the run, its constraints and the strategy choice back to a new run', async () => {
    const started: unknown[] = [];
    server.use(
      show(STRATEGY_DONE),
      metaWithStrategy(),
      http.post(`${API_URL}/api/ideas/extract`, () => HttpResponse.json(EXTRACTED)),
      http.post(`${API_URL}/api/runs`, async ({ request }) => {
        started.push(await request.json());
        return HttpResponse.json({ run_id: 'run-456', state: 'queued' }, { status: 202 });
      }),
      show({ ...STRATEGY_RUNNING, id: 'run-456' }),
    );
    const user = userEvent.setup();
    renderWithApp(
      <Routes>
        <Route path="/" element={<NewValidationPage />} />
        <Route path="/runs/:runId" element={<RunPage />} />
      </Routes>,
      { route: '/runs/run-123' },
    );

    await user.click(await screen.findByRole('button', { name: /edit and re-run/i }));

    expect(await screen.findByLabelText(/your idea/i)).toHaveValue(DONE.submission.idea_description);
    await user.click(screen.getByRole('button', { name: /review my idea/i }));
    await screen.findByRole('heading', { level: 1, name: /review the idea we read/i });

    expect(screen.getByText('Resources and goals (optional)').closest('details')).toHaveAttribute('open');
    expect(screen.getByRole('switch', { name: 'Include strategy' })).toBeChecked();
    expect(screen.getByLabelText('Team size')).toHaveValue('2');
    expect(screen.getByLabelText('Months to first release')).toHaveValue('4');
    expect(screen.getByRole('radio', { name: 'Bootstrapped' })).toBeChecked();
    expect(screen.getByLabelText('Launch region')).toHaveValue('');

    await user.click(screen.getByRole('button', { name: /run analysis/i }));

    await waitFor(() => expect(started).toHaveLength(1));
    expect(started[0]).toEqual({
      submission: DONE.submission,
      idea_override: EXTRACTED,
      include_strategy: true,
      constraints: { team_size: 2, months_to_mvp: 4, budget_level: 'bootstrapped' },
    });
    expect(await screen.findByRole('heading', { name: /analysing/i })).toBeInTheDocument();
  });
});
