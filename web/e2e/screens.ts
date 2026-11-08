/**
 * The screens and states the browser tests cover (KIRO_UI_UPGRADE_SPEC.md Prompt J).
 *
 * One list, used by both the screenshot run and the accessibility run, so the two cannot drift
 * apart: every screen that is photographed is also checked with axe.
 */

import type { Page } from '@playwright/test';

import type { MockOptions } from './mockApi';

export interface Screen {
  /** The file name stem, and the test title. */
  name: string;
  path: string;
  /** What the mocked backend should do for this screen. */
  mock?: MockOptions;
  /** A tab to open, or other work to do once the screen has loaded. */
  after?: (page: Page) => Promise<void>;
  /** Something that must be on screen before the screenshot is taken. */
  ready?: string;
  /** Left out of the accessibility run, with the reason, when it cannot be checked. */
  skipAxe?: string;
}

/** Click one of the result tabs and wait for its panel. */
function openTab(label: string) {
  return async (page: Page): Promise<void> => {
    await page.getByRole('tab', { name: label, exact: true }).click();
    await page.getByRole('tabpanel').waitFor({ state: 'visible' });
  };
}

const RUN = '/runs/run-complete';

export const SCREENS: Screen[] = [
  { name: 'new-validation', path: '/', ready: 'h1:has-text("Check your startup idea")' },

  {
    name: 'new-validation-errors',
    path: '/',
    ready: 'h1:has-text("Check your startup idea")',
    after: async (page) => {
      // Submitting an empty form shows the field messages of Section 6.7.
      await page.getByRole('button', { name: /review my idea/i }).click();
      await page.getByText('Describe your startup idea.').waitFor();
    },
  },

  {
    name: 'new-validation-loading',
    path: '/',
    mock: { hang: ['/api/meta'] },
    ready: '[aria-busy="true"]',
  },

  {
    name: 'new-validation-offline',
    path: '/',
    mock: { offline: true },
    ready: 'text=/start it with/i',
  },

  {
    name: 'review-step',
    path: '/',
    ready: 'h1:has-text("Check your startup idea")',
    after: async (page) => {
      await page.getByLabel(/your idea/i).fill(
        'A platform that reads bank and UPI statements for small businesses and forecasts their cash flow.',
      );
      await page.getByRole('combobox', { name: /industry/i }).click();
      await page.getByRole('option', { name: 'Finance / FinTech' }).click();
      await page.getByLabel(/target customers/i).fill('Small business owners');
      await page.getByLabel(/target customers/i).press('Enter');
      await page.getByRole('button', { name: /review my idea/i }).click();
      await page.getByRole('heading', { name: /review the idea we read/i }).waitFor();
    },
  },

  { name: 'run-progress', path: '/runs/run-running', ready: 'h2:has-text("Analysing:")' },

  { name: 'results-overview', path: RUN, ready: 'h2:has-text("Summary")' },
  { name: 'results-market', path: RUN, ready: '[role=tab]', after: openTab('Market') },
  { name: 'results-competitors', path: RUN, ready: '[role=tab]', after: openTab('Competitors') },
  { name: 'results-sources', path: RUN, ready: '[role=tab]', after: openTab('Sources') },
  { name: 'results-details', path: RUN, ready: '[role=tab]', after: openTab('Run details') },

  {
    name: 'results-source-drawer',
    path: RUN,
    ready: 'h2:has-text("Summary")',
    after: async (page) => {
      await page.getByRole('button', { name: /^Source \d+:/ }).first().click();
      await page.getByRole('dialog').waitFor();
    },
  },

  {
    name: 'results-export-menu',
    path: RUN,
    ready: 'h2:has-text("Summary")',
    after: async (page) => {
      await page.getByRole('button', { name: /export/i }).click();
      await page.getByText('Markdown report').waitFor();
    },
  },

  {
    name: 'results-delete-confirm',
    path: RUN,
    ready: 'h2:has-text("Summary")',
    after: async (page) => {
      await page.getByRole('button', { name: /^delete$/i }).click();
      await page.getByRole('dialog').waitFor();
    },
  },

  { name: 'results-agritech', path: '/runs/run-agritech', ready: 'h2:has-text("Summary")' },
  { name: 'results-partial', path: '/runs/run-partial', ready: 'text=/some parts could not be completed/i' },
  { name: 'results-failed', path: '/runs/run-failed', ready: 'text=/check the text and try again/i' },
  { name: 'results-cancelled', path: '/runs/run-cancelled', ready: 'text=/cancelled before anything was produced/i' },

  {
    name: 'results-loading',
    path: RUN,
    mock: { hang: ['/api/runs/'] },
    ready: '[aria-busy="true"]',
  },

  { name: 'run-missing', path: '/runs/no-such-run', ready: 'h1:has-text("not here")' },

  { name: 'history', path: '/history', ready: 'h1:has-text("History")' },

  {
    name: 'history-empty',
    path: '/history',
    mock: { history: { runs: [] } },
    ready: 'text=/no saved validations yet/i',
  },

  {
    name: 'history-renaming',
    path: '/history',
    ready: 'h1:has-text("History")',
    after: async (page) => {
      await page.getByRole('button', { name: /^rename /i }).first().click();
      await page.getByRole('textbox', { name: /new title for/i }).waitFor();
    },
  },

  {
    name: 'history-loading',
    path: '/history',
    mock: { hang: ['/api/runs'] },
    ready: '[aria-busy="true"]',
  },

  { name: 'status', path: '/status', ready: 'h1:has-text("System status")' },

  {
    name: 'status-offline',
    path: '/status',
    mock: { offline: true },
    ready: 'text=/not reachable/i',
  },

  { name: 'not-found', path: '/nowhere', ready: 'h1:has-text("That page does not exist")' },
];

