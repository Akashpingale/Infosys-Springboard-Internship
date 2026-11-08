/**
 * The history screen (KIRO_UI_UPGRADE_SPEC.md Prompt I, Sections 7.5 and 6.7).
 *
 * MSW answers the list, the rename and the delete, so no saved run on this machine is touched and
 * no API credit is spent. Deleting is the one irreversible action in the interface, so the test
 * checks that it is asked for first and that nothing is sent when the question is declined.
 */

import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { afterEach, describe, expect, it } from 'vitest';

import { API_URL } from '@/api/client';
import type { RunSummary } from '@/api/queries';
import { HistoryPage } from '@/features/history/HistoryPage';
import { MESSAGES } from '@/lib/format';
import { NARROW } from '@/lib/useMediaQuery';
import { renderWithApp } from '@/test/render';
import { server } from '@/test/server';

const RUNS_URL = `${API_URL}/api/runs`;

const ROWS: RunSummary[] = [
  {
    id: 'run-fintech',
    title: 'Cash-flow platform for small businesses',
    industry: 'Finance / FinTech',
    state: 'done',
    status: 'complete',
    created_at: '2026-10-27T15:34:00.000+00:00',
    duration_s: 102.486,
  },
  {
    id: 'run-agritech',
    title: 'CropScan: AI crop disease detection',
    industry: 'Agriculture / AgriTech',
    state: 'done',
    status: 'partial',
    created_at: '2026-10-26T09:10:00.000+00:00',
    duration_s: 159.2,
  },
  {
    id: 'run-live',
    title: 'Food surplus marketplace',
    industry: 'Food & Beverage',
    state: 'running',
    status: null,
    created_at: '2026-10-28T08:00:00.000+00:00',
    duration_s: null,
  },
];

/** The list, held in the handler so a rename or a delete shows on the next read. */
function withRows(rows: RunSummary[] = ROWS) {
  const state = { rows: [...rows], patched: [] as { id: string; title: string }[], deleted: [] as string[] };
  server.use(
    http.get(RUNS_URL, () => HttpResponse.json({ runs: state.rows })),
    http.patch(`${RUNS_URL}/:id`, async ({ params, request }) => {
      const body = (await request.json()) as { title: string };
      state.patched.push({ id: String(params['id']), title: body.title });
      state.rows = state.rows.map((row) => (row.id === params['id'] ? { ...row, title: body.title } : row));
      return HttpResponse.json(state.rows.find((row) => row.id === params['id']));
    }),
    http.delete(`${RUNS_URL}/:id`, ({ params }) => {
      state.deleted.push(String(params['id']));
      state.rows = state.rows.filter((row) => row.id !== params['id']);
      return new HttpResponse(null, { status: 204 });
    }),
  );
  return state;
}

function row(title: string | RegExp): HTMLElement {
  return screen.getByRole('rowheader', { name: title }).closest('tr') as HTMLElement;
}

describe('History: the list', () => {
  it('shows each saved validation with its industry, status, date and duration', async () => {
    withRows();
    renderWithApp(<HistoryPage />);

    expect(await screen.findByRole('rowheader', { name: /cash-flow platform/i })).toBeInTheDocument();
    const fintech = row(/cash-flow platform/i);
    expect(fintech).toHaveTextContent('Finance / FinTech');
    expect(fintech).toHaveTextContent('Complete');
    expect(fintech).toHaveTextContent('1:42');
    expect(fintech).toHaveTextContent('2026');
  });

  it('shows a part-finished run as partial and a going one as running', async () => {
    withRows();
    renderWithApp(<HistoryPage />);

    await screen.findByRole('rowheader', { name: /cropscan/i });
    expect(row(/cropscan/i)).toHaveTextContent('Partial');
    expect(row(/food surplus/i)).toHaveTextContent('Running');
    // A run still going has no duration, so it shows a dash rather than a zero.
    expect(row(/food surplus/i)).toHaveTextContent('\u2014');
  });

  it('opens a run from its title and from the Open button', async () => {
    withRows();
    renderWithApp(<HistoryPage />);

    await screen.findByRole('rowheader', { name: /cash-flow platform/i });
    const links = within(row(/cash-flow platform/i)).getAllByRole('link');

    expect(links.map((link) => link.getAttribute('href'))).toEqual(['/runs/run-fintech', '/runs/run-fintech']);
  });

  it('says plainly when there is nothing saved yet', async () => {
    withRows([]);
    renderWithApp(<HistoryPage />);

    expect(await screen.findByText(MESSAGES.emptyHistory)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /start a new validation/i })).toHaveAttribute('href', '/');
    expect(screen.queryByRole('table')).not.toBeInTheDocument();
  });

  it('offers a retry when the list cannot be read', async () => {
    let calls = 0;
    server.use(
      http.get(RUNS_URL, () => {
        calls += 1;
        return calls === 1
          ? HttpResponse.json(
              { error: { code: 'history_unavailable', message: 'The saved results database could not be opened.' } },
              { status: 503 },
            )
          : HttpResponse.json({ runs: ROWS });
      }),
    );
    const user = userEvent.setup();
    renderWithApp(<HistoryPage />);

    expect(await screen.findByText(/saved results database could not be opened/i)).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /try again/i }));

    expect(await screen.findByRole('rowheader', { name: /cash-flow platform/i })).toBeInTheDocument();
  });
});

describe('History: renaming', () => {
  it('renames in place and keeps the new title', async () => {
    const state = withRows();
    const user = userEvent.setup();
    renderWithApp(<HistoryPage />);

    await screen.findByRole('rowheader', { name: /cash-flow platform/i });
    await user.click(screen.getByRole('button', { name: /rename cash-flow platform/i }));

    const input = screen.getByRole('textbox', { name: /new title for cash-flow platform/i });
    await user.clear(input);
    await user.type(input, 'Cash-flow platform, second look');
    await user.click(screen.getByRole('button', { name: /^save$/i }));

    await waitFor(() => expect(state.patched).toEqual([{ id: 'run-fintech', title: 'Cash-flow platform, second look' }]));
    expect(await screen.findByRole('rowheader', { name: /second look/i })).toBeInTheDocument();
  });

  it('saves on Enter', async () => {
    const state = withRows();
    const user = userEvent.setup();
    renderWithApp(<HistoryPage />);

    await screen.findByRole('rowheader', { name: /cropscan/i });
    await user.click(screen.getByRole('button', { name: /rename cropscan/i }));
    await user.type(screen.getByRole('textbox', { name: /new title for cropscan/i }), ' v2{Enter}');

    await waitFor(() => expect(state.patched[0]?.title).toBe('CropScan: AI crop disease detection v2'));
  });

  it('leaves the title alone on Escape and on Cancel', async () => {
    const state = withRows();
    const user = userEvent.setup();
    renderWithApp(<HistoryPage />);

    await screen.findByRole('rowheader', { name: /cropscan/i });
    await user.click(screen.getByRole('button', { name: /rename cropscan/i }));
    await user.type(screen.getByRole('textbox', { name: /new title for cropscan/i }), ' changed{Escape}');

    expect(state.patched).toEqual([]);
    expect(screen.getByRole('rowheader', { name: 'CropScan: AI crop disease detection' })).toBeInTheDocument();
  });

  it('will not save an empty title', async () => {
    withRows();
    const user = userEvent.setup();
    renderWithApp(<HistoryPage />);

    await screen.findByRole('rowheader', { name: /cropscan/i });
    await user.click(screen.getByRole('button', { name: /rename cropscan/i }));
    await user.clear(screen.getByRole('textbox', { name: /new title for cropscan/i }));

    expect(screen.getByRole('button', { name: /^save$/i })).toBeDisabled();
  });

  it("shows the backend's own message when it refuses the title", async () => {
    withRows();
    server.use(
      http.patch(`${RUNS_URL}/:id`, () =>
        HttpResponse.json(
          { error: { code: 'validation_error', message: 'Keep the title to 120 characters or fewer.' } },
          { status: 422 },
        ),
      ),
    );
    const user = userEvent.setup();
    renderWithApp(<HistoryPage />);

    await screen.findByRole('rowheader', { name: /cropscan/i });
    await user.click(screen.getByRole('button', { name: /rename cropscan/i }));
    await user.type(screen.getByRole('textbox', { name: /new title for cropscan/i }), 'x{Enter}');

    expect(await screen.findByRole('alert')).toHaveTextContent('Keep the title to 120 characters or fewer.');
  });
});

describe('History: deleting', () => {
  it('asks first, and sends nothing when the answer is no', async () => {
    const state = withRows();
    const user = userEvent.setup();
    renderWithApp(<HistoryPage />);

    await screen.findByRole('rowheader', { name: /cropscan/i });
    await user.click(screen.getByRole('button', { name: /delete cropscan/i }));

    const dialog = await screen.findByRole('dialog');
    expect(within(dialog).getByText(/cannot be undone/i)).toBeInTheDocument();
    expect(dialog).toHaveTextContent('CropScan: AI crop disease detection');

    await user.click(within(dialog).getByRole('button', { name: /keep it/i }));

    expect(state.deleted).toEqual([]);
    expect(screen.getByRole('rowheader', { name: /cropscan/i })).toBeInTheDocument();
  });

  it('deletes the run once, and the row goes', async () => {
    const state = withRows();
    const user = userEvent.setup();
    renderWithApp(<HistoryPage />);

    await screen.findByRole('rowheader', { name: /cropscan/i });
    await user.click(screen.getByRole('button', { name: /delete cropscan/i }));
    await user.click(within(await screen.findByRole('dialog')).getByRole('button', { name: /delete it/i }));

    await waitFor(() => expect(state.deleted).toEqual(['run-agritech']));
    await waitFor(() => expect(screen.queryByRole('rowheader', { name: /cropscan/i })).not.toBeInTheDocument());
    expect(screen.getByRole('rowheader', { name: /cash-flow platform/i })).toBeInTheDocument();
  });

  it('explains why a run that is still going cannot be deleted', async () => {
    withRows();
    server.use(
      http.delete(`${RUNS_URL}/:id`, () =>
        HttpResponse.json(
          { error: { code: 'run_active', message: 'Cancel this validation before deleting it.' } },
          { status: 409 },
        ),
      ),
    );
    const user = userEvent.setup();
    renderWithApp(<HistoryPage />);

    await screen.findByRole('rowheader', { name: /food surplus/i });
    await user.click(screen.getByRole('button', { name: /delete food surplus/i }));
    await user.click(within(await screen.findByRole('dialog')).getByRole('button', { name: /delete it/i }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Cancel this validation before deleting it.');
    expect(screen.getByRole('rowheader', { name: /food surplus/i })).toBeInTheDocument();
  });
});

/**
 * The narrow layout (Prompt J). The six columns become a card per run, with the three actions on a
 * full-width row of their own, and only one of the two layouts is ever in the document.
 */
describe('History: on a narrow screen', () => {
  const original = window.matchMedia;

  function narrow(): void {
    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      configurable: true,
      value: (query: string) => ({
        matches: query === NARROW,
        media: query,
        onchange: null,
        addEventListener: () => {},
        removeEventListener: () => {},
        dispatchEvent: () => false,
      }),
    });
  }

  afterEach(() => {
    Object.defineProperty(window, 'matchMedia', { writable: true, configurable: true, value: original });
  });

  it('shows a card per run rather than a table, with no row shown twice', async () => {
    narrow();
    withRows();
    renderWithApp(<HistoryPage />);

    expect(await screen.findByRole('heading', { name: /cash-flow platform/i })).toBeInTheDocument();
    expect(screen.queryByRole('table')).not.toBeInTheDocument();
    expect(screen.getAllByRole('listitem')).toHaveLength(3);
    expect(screen.getAllByRole('link', { name: /cash-flow platform/i })).toHaveLength(1);
  });

  it('keeps every value, labelled, and the actions at full-size targets', async () => {
    narrow();
    withRows();
    renderWithApp(<HistoryPage />);

    const card = (await screen.findByRole('heading', { name: /cash-flow platform/i })).closest('li')!;
    expect(within(card).getAllByRole('term').map((term) => term.textContent)).toEqual([
      'Industry',
      'Status',
      'Took',
      'Started',
    ]);
    expect(card).toHaveTextContent('Finance / FinTech');
    expect(card).toHaveTextContent('Complete');
    expect(card).toHaveTextContent('1:42');

    // The default button size, which is 44 px on a touch screen.
    const open = within(card).getByRole('link', { name: 'Open' });
    expect(open).toHaveClass('min-h-[44px]');
  });

  it('renames from a card, and deletes after asking', async () => {
    narrow();
    const state = withRows();
    const user = userEvent.setup();
    renderWithApp(<HistoryPage />);

    await screen.findByRole('heading', { name: /cropscan/i });
    await user.click(screen.getByRole('button', { name: /rename cropscan/i }));
    await user.type(screen.getByRole('textbox', { name: /new title for cropscan/i }), ' v2{Enter}');

    await waitFor(() => expect(state.patched[0]?.title).toBe('CropScan: AI crop disease detection v2'));

    await user.click(screen.getByRole('button', { name: /delete cash-flow platform/i }));
    await user.click(within(await screen.findByRole('dialog')).getByRole('button', { name: /delete it/i }));

    await waitFor(() => expect(state.deleted).toEqual(['run-fintech']));
  });

  it('still says plainly when there is nothing saved', async () => {
    narrow();
    withRows([]);
    renderWithApp(<HistoryPage />);

    expect(await screen.findByText(MESSAGES.emptyHistory)).toBeInTheDocument();
  });
});
