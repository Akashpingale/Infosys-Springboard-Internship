import type { Page } from '@playwright/test';

import { conversationThread, fullThread, mockApi } from './mockApi';
import { SCREENS, type Screen } from './screens';

export interface M3Screen extends Screen {
  shot?: string;
  targets?: string[];
}

export const TOUCH_WIDTH = 640;
export const MIN_TARGET = 44;

const RESULTS = ['[role=tablist]', '[role=tabpanel]'];
const STRATEGY_RUN = '/runs/run-strategy';
const QUESTION = 'Which risk should I deal with first?';

function openTab(page: Page, label: string): Promise<void> {
  return page
    .getByRole('tab', { name: label, exact: true })
    .click()
    .then(() => page.getByRole('tabpanel').waitFor({ state: 'visible' }));
}

async function openStrategy(page: Page): Promise<void> {
  await openTab(page, 'Strategy');
  await page.getByRole('navigation', { name: 'Strategy sections' }).or(page.getByText('No strategy yet.')).first().waitFor();
}

async function jumpTo(page: Page, section: string): Promise<void> {
  await openStrategy(page);
  await page.getByRole('navigation', { name: 'Strategy sections' }).getByRole('link', { name: section, exact: true }).click();
}

async function openAdvisor(page: Page): Promise<void> {
  await openTab(page, 'Advisor');
  await page.getByRole('textbox', { name: 'Your question' }).or(page.getByText('This conversation is full.')).first().waitFor();
}

async function askAdvisor(page: Page): Promise<void> {
  await openAdvisor(page);
  await page.getByRole('textbox', { name: 'Your question' }).fill(QUESTION);
  await page.getByRole('button', { name: 'Send', exact: true }).click();
}

async function reviewStep(page: Page): Promise<void> {
  const review = SCREENS.find((screen) => screen.name === 'review-step');
  if (!review?.after) {
    throw new Error('The review-step screen is missing from screens.ts.');
  }
  await review.after(page);
}

export async function openScreen(page: Page, screen: M3Screen): Promise<string[]> {
  const asked = await mockApi(page, screen.mock ?? {});
  await page.goto(screen.path);
  if (screen.ready) {
    await page.locator(screen.ready).first().waitFor({ state: 'visible', timeout: 30_000 });
  }
  await screen.after?.(page);
  await page.evaluate(() => document.fonts.ready.then(() => true));
  return asked;
}

export const M3_SCREENS: M3Screen[] = [
  {
    name: 'review-constraints',
    path: '/',
    ready: 'h1:has-text("Check your startup idea")',
    targets: ['section[aria-labelledby="strategy-heading"]'],
    after: async (page) => {
      await reviewStep(page);
      await page.getByText('Resources and goals (optional)').click();
      await page.getByLabel('Team size').waitFor();
    },
  },

  {
    name: 'run-progress-seven-stages',
    path: '/runs/run-strategy-progress',
    ready: 'h2:has-text("Analysing:")',
    after: async (page) => {
      await page.getByText('Planning go-to-market').waitFor();
    },
  },

  {
    name: 'strategy-empty',
    path: '/runs/run-complete',
    ready: '[role=tab]',
    targets: RESULTS,
    after: async (page) => {
      await openStrategy(page);
      await page.getByText('No strategy yet.', { exact: false }).waitFor();
    },
  },

  {
    name: 'strategy-running',
    path: '/runs/run-strategy-running',
    ready: 'h2:has-text("Analysing:")',
    after: async (page) => {
      await page.getByText('Results so far.', { exact: false }).waitFor();
    },
  },

  {
    name: 'strategy-swot-risks',
    path: STRATEGY_RUN,
    ready: '[role=tab]',
    targets: RESULTS,
    after: async (page) => {
      await openStrategy(page);
      await page.getByRole('heading', { name: 'Risks', exact: true }).waitFor();
      await page.getByRole('button', { name: /^Show details/ }).first().click();
      await page.getByRole('button', { name: /^Hide details/ }).first().waitFor();
    },
  },

  {
    name: 'strategy-mvp',
    path: STRATEGY_RUN,
    ready: '[role=tab]',
    shot: '#strategy-mvp',
    targets: RESULTS,
    after: async (page) => {
      await jumpTo(page, 'MVP plan');
      await page.getByText('How the ranking works').click();
    },
  },

  {
    name: 'strategy-gtm',
    path: STRATEGY_RUN,
    ready: '[role=tab]',
    shot: '#strategy-gtm',
    targets: RESULTS,
    after: async (page) => {
      await jumpTo(page, 'Go-to-market');
      await page.getByRole('list', { name: 'Launch plan' }).waitFor();
    },
  },

  {
    name: 'strategy-partial',
    path: '/runs/run-strategy-partial',
    ready: '[role=tab]',
    targets: RESULTS,
    after: async (page) => {
      await openStrategy(page);
      await page.getByText('This part could not be completed.').first().waitFor();
    },
  },

  {
    name: 'strategy-failed',
    path: '/runs/run-strategy-failed',
    ready: '[role=tab]',
    targets: RESULTS,
    after: async (page) => {
      await openStrategy(page);
      await page.getByText('This part could not be completed.').first().waitFor();
    },
  },

  {
    name: 'advisor-empty',
    path: STRATEGY_RUN,
    ready: '[role=tab]',
    targets: RESULTS,
    after: async (page) => {
      await openAdvisor(page);
      await page.getByRole('list', { name: 'Suggested questions' }).waitFor();
    },
  },

  {
    name: 'advisor-conversation',
    path: STRATEGY_RUN,
    mock: { thread: conversationThread() },
    ready: '[role=tab]',
    targets: RESULTS,
    after: async (page) => {
      await openAdvisor(page);
      await page.getByRole('list', { name: 'Follow-up questions' }).waitFor();
    },
  },

  {
    name: 'advisor-pending',
    path: STRATEGY_RUN,
    mock: { ask: 'hang' },
    ready: '[role=tab]',
    targets: RESULTS,
    after: async (page) => {
      await askAdvisor(page);
      await page.getByText('Thinking', { exact: true }).waitFor();
    },
  },

  {
    name: 'advisor-error',
    path: STRATEGY_RUN,
    mock: { ask: 'fail' },
    ready: '[role=tab]',
    targets: RESULTS,
    after: async (page) => {
      await askAdvisor(page);
      await page.getByText('The AI service is busy. Try again in a minute.').waitFor();
    },
  },

  {
    name: 'advisor-full',
    path: STRATEGY_RUN,
    mock: { thread: fullThread() },
    ready: '[role=tab]',
    targets: RESULTS,
    after: async (page) => {
      await openAdvisor(page);
      await page.getByText('This conversation is full.').waitFor();
    },
  },
];
