/**
 * Playwright (KIRO_UI_UPGRADE_SPEC.md Prompt J).
 *
 * Every request to the backend is answered by route interception inside the tests (e2e/mockApi.ts),
 * so these runs never reach a server, never start a validation and never spend an API credit. The
 * only thing served is the built front end.
 *
 * The production build is what is tested, by `vite preview`: the screenshots then show the same CSS
 * and the same split chunks a reader would get, rather than the development server's.
 *
 * Three projects, one per width in Section 6.9: 390 (phone), 820 (tablet) and 1440 (desktop).
 */

import { defineConfig, devices } from '@playwright/test';

export const WIDTHS = [390, 820, 1440] as const;
export const PREVIEW_PORT = 4173;
export const BASE_URL = `http://127.0.0.1:${PREVIEW_PORT}`;

/** Where Section 6.9's screenshots are written, outside web/ as the specification asks. */
export const SHOTS_DIR = '../docs/assets/ui_v2';

export default defineConfig({
  testDir: './e2e',
  testMatch: /.*\.spec\.ts$/,
  // The screenshot run writes files; two workers writing the same file would race.
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env['CI'],
  retries: 0,
  reporter: [['list'], ['json', { outputFile: 'e2e-results.json' }]],
  timeout: 60_000,
  expect: { timeout: 10_000 },
  outputDir: 'test-results',

  use: {
    baseURL: BASE_URL,
    // A real browser, not the headless shell, so the print stylesheet and fonts behave normally.
    channel: 'chromium',
    headless: true,
    screenshot: 'off',
    video: 'off',
    trace: 'retain-on-failure',
  },

  projects: WIDTHS.map((width) => ({
    name: `w${width}`,
    use: {
      ...devices['Desktop Chrome'],
      channel: 'chromium',
      viewport: { width, height: 900 },
      isMobile: false,
      hasTouch: width < 640,
    },
  })),

  webServer: {
    command: `npm run preview -- --port ${PREVIEW_PORT} --strictPort --host 127.0.0.1`,
    url: BASE_URL,
    reuseExistingServer: true,
    timeout: 120_000,
    stdout: 'ignore',
    stderr: 'pipe',
  },
});
