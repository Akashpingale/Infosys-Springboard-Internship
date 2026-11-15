import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { API_URL } from '@/api/client';
import type { MetaResponse } from '@/api/queries';
import { NewValidationPage } from '@/features/new-validation/NewValidationPage';
import {
  EMPTY_CONSTRAINTS,
  constraintsFormSchema,
  fromConstraints,
  reviewStepSchema,
  toConstraints,
} from '@/features/new-validation/schema';
import { EXTRACTED, META, VALID_IDEA } from '@/test/fixtures';
import { renderWithApp } from '@/test/render';
import { server } from '@/test/server';
import { META_WITH_STRATEGY, metaWithStrategy } from '@/test/strategyHandlers';

const navigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return { ...actual, useNavigate: () => navigate };
});

beforeEach(() => navigate.mockReset());

const SUBMISSION = {
  idea_description: VALID_IDEA,
  industry: 'Agriculture / AgriTech',
  target_customers: 'Small farmers',
  relevant_details: null,
};

const LIMITS = META_WITH_STRATEGY.strategy!.constraints;

function extractOk() {
  return http.post(`${API_URL}/api/ideas/extract`, () => HttpResponse.json(EXTRACTED));
}

function runOk(sent: unknown[]) {
  return http.post(`${API_URL}/api/runs`, async ({ request }) => {
    sent.push(await request.json());
    return HttpResponse.json({ run_id: 'run-123', state: 'queued' }, { status: 202 });
  });
}

async function reachReview(user: ReturnType<typeof userEvent.setup>): Promise<void> {
  await user.type(await screen.findByLabelText(/your idea/i), VALID_IDEA);
  await user.click(screen.getByRole('combobox', { name: /industry/i }));
  await user.click(await screen.findByRole('option', { name: 'Agriculture / AgriTech' }));
  await user.type(screen.getByLabelText(/target customers/i), 'Small farmers{Enter}');
  await user.click(screen.getByRole('button', { name: /review my idea/i }));
  await screen.findByRole('heading', { level: 1, name: /review the idea we read/i });
}

function panel(): HTMLDetailsElement {
  return screen.getByText('Resources and goals (optional)').closest('details') as HTMLDetailsElement;
}

describe('Review step: the strategy switch', () => {
  it('is on by default and says what it costs', async () => {
    server.use(metaWithStrategy(), extractOk());
    const user = userEvent.setup();
    renderWithApp(<NewValidationPage />);
    await reachReview(user);

    const toggle = screen.getByRole('switch', { name: 'Include strategy' });
    expect(toggle).toBeChecked();
    expect(toggle).toHaveAccessibleDescription(
      'Adds a SWOT and risk review, an MVP plan and a go-to-market plan. Uses 3 more AI requests and about 1 to 2 minutes.',
    );
  });

  it('sends the switch and no constraints when none was given', async () => {
    const sent: unknown[] = [];
    server.use(metaWithStrategy(), extractOk(), runOk(sent));
    const user = userEvent.setup();
    renderWithApp(<NewValidationPage />);
    await reachReview(user);

    await user.click(screen.getByRole('button', { name: /run analysis/i }));

    await waitFor(() => expect(sent).toHaveLength(1));
    expect(sent[0]).toEqual({ submission: SUBMISSION, idea_override: EXTRACTED, include_strategy: true });
    expect(navigate).toHaveBeenCalledWith('/runs/run-123');
  });

  it('sends neither strategy nor constraints when it is switched off', async () => {
    const sent: unknown[] = [];
    server.use(metaWithStrategy(), extractOk(), runOk(sent));
    const user = userEvent.setup();
    renderWithApp(<NewValidationPage />);
    await reachReview(user);

    await user.click(screen.getByText('Resources and goals (optional)'));
    await user.selectOptions(screen.getByLabelText('Team size'), '4');
    await user.click(screen.getByRole('switch', { name: 'Include strategy' }));

    expect(screen.queryByText('Resources and goals (optional)')).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /run analysis/i }));

    await waitFor(() => expect(sent).toHaveLength(1));
    expect(sent[0]).toEqual({ submission: SUBMISSION, idea_override: EXTRACTED, include_strategy: false });
  });

  it('is not offered when the backend has no strategy, and the request is the one sent before', async () => {
    const sent: unknown[] = [];
    server.use(
      http.get(`${API_URL}/api/meta`, () => HttpResponse.json(META)),
      extractOk(),
      runOk(sent),
    );
    const user = userEvent.setup();
    renderWithApp(<NewValidationPage />);
    await reachReview(user);

    expect(screen.queryByRole('switch')).not.toBeInTheDocument();
    expect(screen.queryByText('Resources and goals (optional)')).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /run analysis/i }));

    await waitFor(() => expect(sent).toHaveLength(1));
    expect(sent[0]).toEqual({ submission: SUBMISSION, idea_override: EXTRACTED });
  });

  it('is not offered when the backend reports strategy as unavailable', async () => {
    const unavailable: MetaResponse = {
      ...META_WITH_STRATEGY,
      strategy: { ...META_WITH_STRATEGY.strategy!, available: false },
    };
    server.use(metaWithStrategy(unavailable), extractOk());
    const user = userEvent.setup();
    renderWithApp(<NewValidationPage />);
    await reachReview(user);

    expect(screen.queryByRole('switch')).not.toBeInTheDocument();
  });
});

describe('Review step: resources and goals', () => {
  it('is closed by default and states the assumption', async () => {
    server.use(metaWithStrategy(), extractOk());
    const user = userEvent.setup();
    renderWithApp(<NewValidationPage />);
    await reachReview(user);

    expect(panel()).not.toHaveAttribute('open');
    expect(panel()).toHaveTextContent(
      'If you skip these, the plan assumes a team of 2 and 3 months, and marks that as an assumption.',
    );
  });

  it('offers the fields and choices the plan names', async () => {
    server.use(metaWithStrategy(), extractOk());
    const user = userEvent.setup();
    renderWithApp(<NewValidationPage />);
    await reachReview(user);
    await user.click(screen.getByText('Resources and goals (optional)'));

    const team = screen.getByLabelText('Team size') as HTMLSelectElement;
    expect([...team.options].map((option) => option.text)).toEqual([
      'Not set',
      '1 person',
      ...Array.from({ length: 9 }, (_, index) => `${index + 2} people`),
    ]);
    expect(team).toHaveDisplayValue('Not set');
    const months = screen.getByLabelText('Months to first release') as HTMLSelectElement;
    expect(months.options).toHaveLength(13);
    expect(months).toHaveDisplayValue('Not set');
    const budget = screen.getByRole('group', { name: 'Budget level' });
    expect(budget).toHaveTextContent('BootstrappedSmall budgetFunded');
    const skill = screen.getByRole('group', { name: 'Technical skill' });
    expect(skill).toHaveTextContent('Non-technicalSome technicalStrong technical team');
    expect(screen.getByLabelText('Launch region')).toHaveAccessibleDescription('Optional, up to 60 characters.');
  });

  it('sends only the fields that were filled, trimmed and typed as the backend expects', async () => {
    const sent: unknown[] = [];
    server.use(metaWithStrategy(), extractOk(), runOk(sent));
    const user = userEvent.setup();
    renderWithApp(<NewValidationPage />);
    await reachReview(user);

    await user.click(screen.getByText('Resources and goals (optional)'));
    await user.selectOptions(screen.getByLabelText('Team size'), '3');
    await user.click(screen.getByRole('radio', { name: 'Bootstrapped' }));
    await user.type(screen.getByLabelText('Launch region'), '  Pune, India  ');
    await user.click(screen.getByRole('button', { name: /run analysis/i }));

    await waitFor(() => expect(sent).toHaveLength(1));
    expect(sent[0]).toEqual({
      submission: SUBMISSION,
      idea_override: EXTRACTED,
      include_strategy: true,
      constraints: { team_size: 3, budget_level: 'bootstrapped', launch_region: 'Pune, India' },
    });
  });

  it('takes its options and limits from /api/meta, and refuses what they do not allow', async () => {
    const sent: unknown[] = [];
    const narrow: MetaResponse = {
      ...META_WITH_STRATEGY,
      strategy: {
        ...META_WITH_STRATEGY.strategy!,
        constraints: {
          team_size: { min_value: 1, max_value: 4 },
          months_to_mvp: { min_value: 2, max_value: 6 },
          launch_region: { min_chars: null, max_chars: 10, min_words: null },
          budget_levels: ['bootstrapped', 'funded'],
          technical_skills: ['some'],
        },
      },
    };
    server.use(metaWithStrategy(narrow), extractOk(), runOk(sent));
    const user = userEvent.setup();
    renderWithApp(<NewValidationPage />);
    await reachReview(user);
    await user.click(screen.getByText('Resources and goals (optional)'));

    const team = screen.getByLabelText('Team size');
    expect([...(team as HTMLSelectElement).options].map((option) => option.value)).toEqual(['', '1', '2', '3', '4']);
    const months = screen.getByLabelText('Months to first release');
    expect([...(months as HTMLSelectElement).options].map((option) => option.value)).toEqual([
      '',
      '2',
      '3',
      '4',
      '5',
      '6',
    ]);
    expect(screen.getAllByRole('radio').map((radio) => (radio as HTMLInputElement).value)).toEqual([
      'bootstrapped',
      'funded',
      'some',
    ]);

    await user.type(screen.getByLabelText('Launch region'), 'Maharashtra');
    await user.click(screen.getByRole('button', { name: /run analysis/i }));

    expect(await screen.findByText('Keep the launch region to 10 characters or fewer.')).toBeInTheDocument();
    expect(screen.getByLabelText('Launch region')).toHaveAttribute('aria-invalid', 'true');
    expect(sent).toHaveLength(0);
  });
});

describe('Edit and re-run: the constraints come back', () => {
  const PREFILL = {
    idea_description: VALID_IDEA,
    industry: 'Agriculture / AgriTech',
    target_customers: 'Small farmers',
    relevant_details: null,
  };
  const CARRIED = {
    team_size: 3,
    months_to_mvp: 6,
    budget_level: 'small' as const,
    technical_skill: 'strong' as const,
    launch_region: 'Pune',
  };

  it('opens the panel on the stored constraints and sends them again', async () => {
    const sent: unknown[] = [];
    server.use(metaWithStrategy(), extractOk(), runOk(sent));
    const user = userEvent.setup();
    renderWithApp(<NewValidationPage />, { state: { prefill: PREFILL, constraints: CARRIED } });

    await user.click(await screen.findByRole('button', { name: /review my idea/i }));
    await screen.findByRole('heading', { level: 1, name: /review the idea we read/i });

    expect(panel()).toHaveAttribute('open');
    expect(screen.getByLabelText('Team size')).toHaveValue('3');
    expect(screen.getByLabelText('Months to first release')).toHaveValue('6');
    expect(screen.getByRole('radio', { name: 'Small budget' })).toBeChecked();
    expect(screen.getByRole('radio', { name: 'Strong technical team' })).toBeChecked();
    expect(screen.getByLabelText('Launch region')).toHaveValue('Pune');

    await user.click(screen.getByRole('button', { name: /run analysis/i }));

    await waitFor(() => expect(sent).toHaveLength(1));
    expect(sent[0]).toEqual({
      submission: PREFILL,
      idea_override: EXTRACTED,
      include_strategy: true,
      constraints: CARRIED,
    });
  });

  it('keeps the panel closed when the earlier run had no constraints', async () => {
    server.use(metaWithStrategy(), extractOk());
    const user = userEvent.setup();
    renderWithApp(<NewValidationPage />, { state: { prefill: PREFILL, constraints: null } });

    await user.click(await screen.findByRole('button', { name: /review my idea/i }));
    await screen.findByRole('heading', { level: 1, name: /review the idea we read/i });

    expect(panel()).not.toHaveAttribute('open');
  });
});

describe('Constraint rules', () => {
  const schema = constraintsFormSchema(LIMITS);

  function messages(values: Partial<typeof EMPTY_CONSTRAINTS>): string[] {
    const parsed = schema.safeParse({ ...EMPTY_CONSTRAINTS, ...values });
    return parsed.success ? [] : parsed.error.issues.map((issue) => issue.message);
  }

  it('accepts a form left empty', () => {
    expect(messages({})).toEqual([]);
  });

  it('builds its messages from the limits the backend reported', () => {
    expect(messages({ team_size: '11' })).toEqual(['Choose a team size from 1 to 10.']);
    expect(messages({ months_to_mvp: '0' })).toEqual(['Choose from 1 to 12 months.']);
    expect(messages({ team_size: '2.5' })).toEqual(['Choose a team size from 1 to 10.']);
    expect(messages({ budget_level: 'huge' })).toEqual(['Choose one of the budget levels.']);
    expect(messages({ technical_skill: 'expert' })).toEqual(['Choose one of the skill levels.']);
    expect(messages({ launch_region: 'x'.repeat(61) })).toEqual(['Keep the launch region to 60 characters or fewer.']);
    expect(messages({ launch_region: ` ${'x'.repeat(60)} ` })).toEqual([]);
  });

  it('checks the constraints in the review step only while strategy is switched on', () => {
    const review = reviewStepSchema(META_WITH_STRATEGY.limits, LIMITS);
    const values = {
      idea_title: 'CropScan',
      problem: 'Crops are lost.',
      solution: 'An app diagnoses them.',
      industry: 'Agriculture / AgriTech',
      target_customers: ['Small farmers'],
      key_features: ['One', 'Two', 'Three'],
      constraints: { ...EMPTY_CONSTRAINTS, team_size: '40' },
    };

    const on = review.safeParse({ ...values, include_strategy: true });
    expect(on.success === false && on.error.issues.map((issue) => [issue.path.join('.'), issue.message])).toEqual([
      ['constraints.team_size', 'Choose a team size from 1 to 10.'],
    ]);
    expect(review.safeParse({ ...values, include_strategy: false }).success).toBe(true);
    expect(reviewStepSchema(META_WITH_STRATEGY.limits, null).safeParse({ ...values, include_strategy: true }).success).toBe(
      true,
    );
  });

  it('keeps only the filled fields, and gives null when none was filled', () => {
    expect(toConstraints(EMPTY_CONSTRAINTS)).toBeNull();
    expect(toConstraints({ ...EMPTY_CONSTRAINTS, launch_region: '   ' })).toBeNull();
    expect(toConstraints({ ...EMPTY_CONSTRAINTS, months_to_mvp: '5', technical_skill: 'some' })).toEqual({
      months_to_mvp: 5,
      technical_skill: 'some',
    });
  });

  it('turns stored constraints back into the form and back again', () => {
    const stored = {
      team_size: 2,
      months_to_mvp: 4,
      budget_level: 'funded' as const,
      technical_skill: 'non_technical' as const,
      launch_region: 'Kenya',
    };
    expect(fromConstraints(stored)).toEqual({
      team_size: '2',
      months_to_mvp: '4',
      budget_level: 'funded',
      technical_skill: 'non_technical',
      launch_region: 'Kenya',
    });
    expect(toConstraints(fromConstraints(stored))).toEqual(stored);
    expect(fromConstraints(null)).toEqual(EMPTY_CONSTRAINTS);
    expect(fromConstraints({ team_size: null, budget_level: null })).toEqual(EMPTY_CONSTRAINTS);
  });
});
