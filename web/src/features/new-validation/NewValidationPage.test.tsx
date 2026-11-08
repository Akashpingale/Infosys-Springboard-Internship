/**
 * The submission flow end to end, with MSW standing in for the backend (no live call, ever).
 *
 * Covers the success path through form, review and run, and each failure the backend can answer
 * with: an unreachable server, a 422 the form did not catch, extraction failing, and the 409 that
 * means another validation is already running.
 */

import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { describe, expect, it, vi } from 'vitest';

import { API_URL } from '@/api/client';
import { NewValidationPage } from '@/features/new-validation/NewValidationPage';
import { EXTRACTED, META, VALID_IDEA } from '@/test/fixtures';
import { renderWithApp } from '@/test/render';
import { server } from '@/test/server';

const navigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return { ...actual, useNavigate: () => navigate };
});

function metaOk() {
  return http.get(`${API_URL}/api/meta`, () => HttpResponse.json(META));
}

function extractOk(capture?: (body: unknown) => void) {
  return http.post(`${API_URL}/api/ideas/extract`, async ({ request }) => {
    capture?.(await request.json());
    return HttpResponse.json(EXTRACTED);
  });
}

function runOk(capture?: (body: unknown) => void) {
  return http.post(`${API_URL}/api/runs`, async ({ request }) => {
    capture?.(await request.json());
    return HttpResponse.json({ run_id: 'run-123', state: 'queued' }, { status: 202 });
  });
}

/** Fill the form with a valid idea and submit it. */
async function fillAndSubmit(user: ReturnType<typeof userEvent.setup>): Promise<void> {
  await user.type(screen.getByLabelText(/your idea/i), VALID_IDEA);
  await user.click(screen.getByRole('combobox', { name: /industry/i }));
  await user.click(await screen.findByRole('option', { name: 'Agriculture / AgriTech' }));
  await user.type(screen.getByLabelText(/target customers/i), 'Small farmers{Enter}');
  await user.click(screen.getByRole('button', { name: /review my idea/i }));
}

describe('New validation: the form', () => {
  it('shows the limits the backend reported, rather than its own numbers', async () => {
    server.use(metaOk());
    renderWithApp(<NewValidationPage />);

    expect(await screen.findByText('30 to 2000 characters, at least 3 words.')).toBeInTheDocument();
    expect(screen.getByText('Optional, up to 1500 characters.')).toBeInTheDocument();
  });

  it('refuses an empty submission with plain messages and calls nothing', async () => {
    const extract = vi.fn();
    server.use(metaOk(), extractOk(extract));
    const user = userEvent.setup();
    renderWithApp(<NewValidationPage />);

    await user.click(await screen.findByRole('button', { name: /review my idea/i }));

    expect(await screen.findByText('Describe your startup idea.')).toBeInTheDocument();
    expect(screen.getByText('Choose an industry, or type your own.')).toBeInTheDocument();
    expect(screen.getByText('Add at least one target customer.')).toBeInTheDocument();
    expect(extract).not.toHaveBeenCalled();
  });

  it('tells the founder when the idea is too short', async () => {
    server.use(metaOk(), extractOk());
    const user = userEvent.setup();
    renderWithApp(<NewValidationPage />);

    await user.type(await screen.findByLabelText(/your idea/i), 'Too short an idea');
    await user.click(screen.getByRole('button', { name: /review my idea/i }));

    expect(await screen.findByText('Describe your idea in at least 30 characters.')).toBeInTheDocument();
  });

  it('counts the characters as they are typed', async () => {
    server.use(metaOk());
    const user = userEvent.setup();
    renderWithApp(<NewValidationPage />);

    await user.type(await screen.findByLabelText(/your idea/i), 'Hello');

    expect(screen.getByText('5 / 2000')).toBeInTheDocument();
  });

  it('fills itself from an example idea', async () => {
    server.use(metaOk());
    const user = userEvent.setup();
    renderWithApp(<NewValidationPage />);

    await user.click(await screen.findByRole('button', { name: 'Agritech' }));

    expect(screen.getByLabelText(/your idea/i)).toHaveValue(META.examples[0]!.submission.idea_description);
    expect(screen.getByRole('combobox', { name: /industry/i })).toHaveTextContent('Agriculture / AgriTech');
    expect(screen.getByText('Small farmers in India')).toBeInTheDocument();
    expect(screen.getByText('Agricultural cooperatives')).toBeInTheDocument();
  });

  it('keeps the optional context folded away until it is wanted', async () => {
    server.use(metaOk());
    renderWithApp(<NewValidationPage />);

    const summary = await screen.findByText(/add more context/i);
    expect(summary.closest('details')).not.toHaveAttribute('open');
  });
});

describe('New validation: the industry combobox', () => {
  it('lists the industries from the backend and leaves out the catch-all', async () => {
    server.use(metaOk());
    const user = userEvent.setup();
    renderWithApp(<NewValidationPage />);

    await user.click(await screen.findByRole('combobox', { name: /industry/i }));

    expect(await screen.findByRole('option', { name: 'Agriculture / AgriTech' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Finance / FinTech' })).toBeInTheDocument();
    expect(screen.queryByRole('option', { name: 'Other' })).not.toBeInTheDocument();
  });

  it('accepts an industry that is not on the list', async () => {
    const sent: unknown[] = [];
    server.use(metaOk(), extractOk((body) => sent.push(body)));
    const user = userEvent.setup();
    renderWithApp(<NewValidationPage />);

    await user.type(await screen.findByLabelText(/your idea/i), VALID_IDEA);
    await user.click(screen.getByRole('combobox', { name: /industry/i }));
    await user.type(screen.getByPlaceholderText(/search or type your industry/i), 'Sports and fitness');
    await user.click(await screen.findByRole('option', { name: /use your own/i }));
    await user.type(screen.getByLabelText(/target customers/i), 'Runners{Enter}');
    await user.click(screen.getByRole('button', { name: /review my idea/i }));

    await waitFor(() => expect(sent).toHaveLength(1));
    expect(sent[0]).toMatchObject({ industry: 'Sports and fitness' });
  });

  it('searches the list', async () => {
    server.use(metaOk());
    const user = userEvent.setup();
    renderWithApp(<NewValidationPage />);

    await user.click(await screen.findByRole('combobox', { name: /industry/i }));
    await user.type(screen.getByPlaceholderText(/search or type your industry/i), 'health');

    expect(await screen.findByRole('option', { name: 'Healthcare / HealthTech' })).toBeInTheDocument();
    expect(screen.queryByRole('option', { name: 'Finance / FinTech' })).not.toBeInTheDocument();
  });
});

describe('New validation: the customer chips', () => {
  it('turns what is typed into chips and removes them again', async () => {
    server.use(metaOk());
    const user = userEvent.setup();
    renderWithApp(<NewValidationPage />);

    const input = await screen.findByLabelText(/target customers/i);
    await user.type(input, 'Small farmers{Enter}Cooperatives{Enter}');

    expect(screen.getByText('Small farmers')).toBeInTheDocument();
    expect(screen.getByText('Cooperatives')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Remove Small farmers' }));

    expect(screen.queryByText('Small farmers')).not.toBeInTheDocument();
    expect(screen.getByText('Cooperatives')).toBeInTheDocument();
  });

  it('refuses a duplicate', async () => {
    server.use(metaOk());
    const user = userEvent.setup();
    renderWithApp(<NewValidationPage />);

    const input = await screen.findByLabelText(/target customers/i);
    await user.type(input, 'Small farmers{Enter}small FARMERS{Enter}');

    expect(screen.getAllByText(/small farmers/i)).toHaveLength(1);
  });

  it('joins the chips into the one field the backend takes', async () => {
    const sent: unknown[] = [];
    server.use(metaOk(), extractOk((body) => sent.push(body)));
    const user = userEvent.setup();
    renderWithApp(<NewValidationPage />);

    await user.type(await screen.findByLabelText(/your idea/i), VALID_IDEA);
    await user.click(screen.getByRole('combobox', { name: /industry/i }));
    await user.click(await screen.findByRole('option', { name: 'Agriculture / AgriTech' }));
    await user.type(screen.getByLabelText(/target customers/i), 'Small farmers{Enter}Cooperatives{Enter}');
    await user.click(screen.getByRole('button', { name: /review my idea/i }));

    await waitFor(() => expect(sent).toHaveLength(1));
    expect(sent[0]).toMatchObject({ target_customers: 'Small farmers, Cooperatives' });
  });
});

describe('New validation: the review step', () => {
  it('shows what was written beside what was understood, and starts the run with the edited idea', async () => {
    const started: unknown[] = [];
    server.use(metaOk(), extractOk(), runOk((body) => started.push(body)));
    const user = userEvent.setup();
    renderWithApp(<NewValidationPage />);

    await screen.findByLabelText(/your idea/i);
    await fillAndSubmit(user);

    expect(await screen.findByRole('heading', { level: 1, name: /review the idea we read/i })).toBeInTheDocument();
    const wrote = screen.getByRole('region', { name: /what you wrote/i });
    expect(within(wrote).getByText(VALID_IDEA)).toBeInTheDocument();
    expect(screen.getByLabelText(/^title/i)).toHaveValue(EXTRACTED.idea_title);

    await user.clear(screen.getByLabelText(/^title/i));
    await user.type(screen.getByLabelText(/^title/i), 'Corrected title');
    await user.click(screen.getByRole('button', { name: /run analysis/i }));

    await waitFor(() => expect(started).toHaveLength(1));
    expect(started[0]).toMatchObject({
      idea_override: { idea_title: 'Corrected title', problem: EXTRACTED.problem },
      submission: { idea_description: VALID_IDEA },
    });
    expect(navigate).toHaveBeenCalledWith('/runs/run-123');
  });

  it('says how long the analysis takes before it starts', async () => {
    server.use(metaOk(), extractOk(), runOk());
    const user = userEvent.setup();
    renderWithApp(<NewValidationPage />);

    await screen.findByLabelText(/your idea/i);
    await fillAndSubmit(user);

    expect(await screen.findByText(/takes about two minutes/i)).toBeInTheDocument();
  });

  it('lets a feature be added and removed within the allowed range', async () => {
    server.use(metaOk(), extractOk(), runOk());
    const user = userEvent.setup();
    renderWithApp(<NewValidationPage />);

    await screen.findByLabelText(/your idea/i);
    await fillAndSubmit(user);
    await screen.findByLabelText('Key feature 1');

    await user.click(screen.getByRole('button', { name: /add a feature/i }));
    expect(screen.getByLabelText('Key feature 4')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Remove key feature 4' }));
    expect(screen.queryByLabelText('Key feature 4')).not.toBeInTheDocument();
  });

  it('will not let the minimum number of features be broken', async () => {
    server.use(metaOk(), extractOk(), runOk());
    const user = userEvent.setup();
    renderWithApp(<NewValidationPage />);

    await screen.findByLabelText(/your idea/i);
    await fillAndSubmit(user);
    await screen.findByLabelText('Key feature 1');

    // Three features is the minimum, so none of them can be removed.
    for (const index of [1, 2, 3]) {
      expect(screen.getByRole('button', { name: `Remove key feature ${index}` })).toBeDisabled();
    }
  });

  it('goes back to the form with what was typed still there', async () => {
    server.use(metaOk(), extractOk(), runOk());
    const user = userEvent.setup();
    renderWithApp(<NewValidationPage />);

    await screen.findByLabelText(/your idea/i);
    await fillAndSubmit(user);
    await user.click(await screen.findByRole('button', { name: 'Back' }));

    expect(await screen.findByLabelText(/your idea/i)).toHaveValue(VALID_IDEA);
    expect(screen.getByText('Small farmers')).toBeInTheDocument();
  });
});

describe('New validation: failures', () => {
  it('says how to start the server when it cannot be reached', async () => {
    server.use(metaOk(), http.post(`${API_URL}/api/ideas/extract`, () => HttpResponse.error()));
    const user = userEvent.setup();
    renderWithApp(<NewValidationPage />);

    await screen.findByLabelText(/your idea/i);
    await fillAndSubmit(user);

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent(/the server is not running/i);
    expect(alert).toHaveTextContent(/python app\.py/);
    expect(screen.queryByRole('heading', { name: /review the idea/i })).not.toBeInTheDocument();
  });

  it("passes on the backend's own words when the form slips past the browser", async () => {
    server.use(
      metaOk(),
      http.post(`${API_URL}/api/ideas/extract`, () =>
        HttpResponse.json(
          { error: { code: 'invalid_input', message: 'idea_description: String should have at least 30 characters' } },
          { status: 422 },
        ),
      ),
    );
    const user = userEvent.setup();
    renderWithApp(<NewValidationPage />);

    await screen.findByLabelText(/your idea/i);
    await fillAndSubmit(user);

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent(/the server rejected the form/i);
    expect(alert).toHaveTextContent(/at least 30 characters/);
  });

  it('reports a failed extraction without a stack trace, and stays on the form', async () => {
    server.use(
      metaOk(),
      http.post(`${API_URL}/api/ideas/extract`, () =>
        HttpResponse.json(
          { error: { code: 'llm_api_error', message: 'The AI service is busy right now. Please try again in a minute.' } },
          { status: 502 },
        ),
      ),
    );
    const user = userEvent.setup();
    renderWithApp(<NewValidationPage />);

    await screen.findByLabelText(/your idea/i);
    await fillAndSubmit(user);

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('The AI service is busy right now. Please try again in a minute.');
    expect(alert).not.toHaveTextContent(/traceback/i);
    expect(screen.getByLabelText(/your idea/i)).toBeInTheDocument();
  });

  it('explains the concurrency limit and keeps the review open so the run can be retried', async () => {
    server.use(
      metaOk(),
      extractOk(),
      http.post(`${API_URL}/api/runs`, () =>
        HttpResponse.json(
          { error: { code: 'run_limit_reached', message: 'A validation is already running. Try again when it has finished.' } },
          { status: 409 },
        ),
      ),
    );
    const user = userEvent.setup();
    renderWithApp(<NewValidationPage />);

    await screen.findByLabelText(/your idea/i);
    await fillAndSubmit(user);
    await user.click(await screen.findByRole('button', { name: /run analysis/i }));

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent(/a validation is already running/i);
    expect(navigate).not.toHaveBeenCalled();
    expect(screen.getByRole('button', { name: /run analysis/i })).toBeEnabled();
  });

  it('offers a retry when the limits themselves cannot be loaded', async () => {
    server.use(http.get(`${API_URL}/api/meta`, () => HttpResponse.error()));
    renderWithApp(<NewValidationPage />);

    const alert = await screen.findByRole('alert', {}, { timeout: 5000 });
    expect(alert).toHaveTextContent(/the server is not running/i);
    expect(screen.getByRole('button', { name: /try again/i })).toBeInTheDocument();
    expect(screen.queryByLabelText(/your idea/i)).not.toBeInTheDocument();
  });

  it('blocks a second submission while the first is in flight', async () => {
    let calls = 0;
    server.use(
      metaOk(),
      http.post(`${API_URL}/api/ideas/extract`, async () => {
        calls += 1;
        await new Promise((resolve) => setTimeout(resolve, 150));
        return HttpResponse.json(EXTRACTED);
      }),
      runOk(),
    );
    const user = userEvent.setup();
    renderWithApp(<NewValidationPage />);

    await screen.findByLabelText(/your idea/i);
    await fillAndSubmit(user);

    const button = screen.getByRole('button', { name: /reading your idea/i });
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute('aria-busy', 'true');

    await user.click(button);
    await screen.findByRole('heading', { level: 1, name: /review the idea we read/i });
    expect(calls).toBe(1);
  });
});

/**
 * Edit and re-run (Prompt I): the results header sends the saved submission here in the router's
 * state, and the form opens on it. The earlier run is not touched, and nothing is started until the
 * founder submits as usual.
 */
describe('New validation: edit and re-run', () => {
  const PREFILL = {
    idea_description:
      'A platform that reads bank and UPI statements for small businesses and forecasts their cash flow.',
    industry: 'Finance / FinTech',
    target_customers: 'Small business owners, Accountants',
    relevant_details: 'Starting with shops in Pune.',
  };

  it('opens the form on the earlier submission, with the customers back as chips', async () => {
    server.use(metaOk());
    renderWithApp(<NewValidationPage />, { state: { prefill: PREFILL } });

    expect(await screen.findByLabelText(/your idea/i)).toHaveValue(PREFILL.idea_description);
    expect(screen.getByRole('combobox', { name: /industry/i })).toHaveTextContent('Finance / FinTech');
    expect(screen.getByLabelText(/anything else/i)).toHaveValue('Starting with shops in Pune.');
    // The panel is open, so carried context is visible rather than hidden behind a toggle.
    expect(screen.getByText(/add more context/i).closest('details')).toHaveAttribute('open');
    // The one stored string becomes the two chips it was typed as.
    expect(screen.getByText('Small business owners')).toBeInTheDocument();
    expect(screen.getByText('Accountants')).toBeInTheDocument();
  });

  it('says where the text came from and that a new validation will be made', async () => {
    server.use(metaOk());
    renderWithApp(<NewValidationPage />, { state: { prefill: PREFILL } });

    const note = await screen.findByText(/loaded from an earlier validation/i);
    expect(note.closest('[role="status"]')).toHaveTextContent(/leaves the earlier one as it is/i);
  });

  it('starts nothing by itself: the founder still submits', async () => {
    const extract = vi.fn();
    const started = vi.fn();
    server.use(metaOk(), extractOk(extract), runOk(started));
    renderWithApp(<NewValidationPage />, { state: { prefill: PREFILL } });

    await screen.findByLabelText(/your idea/i);

    expect(extract).not.toHaveBeenCalled();
    expect(started).not.toHaveBeenCalled();
    expect(navigate).not.toHaveBeenCalled();
  });

  it('shows an empty form when nothing was carried', async () => {
    server.use(metaOk());
    renderWithApp(<NewValidationPage />);

    expect(await screen.findByLabelText(/your idea/i)).toHaveValue('');
    expect(screen.queryByText(/loaded from an earlier validation/i)).not.toBeInTheDocument();
  });
});
