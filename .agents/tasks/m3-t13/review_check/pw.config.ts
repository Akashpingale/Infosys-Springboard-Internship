import { defineConfig, devices } from '../../../../web/node_modules/@playwright/test/index.mjs';

export default defineConfig({
  testDir: '.',
  testMatch: /tabs-scroll\.spec\.ts$/,
  workers: 1,
  retries: 0,
  reporter: [['list']],
  timeout: 60_000,
  outputDir: './out',
  use: { baseURL: 'http://127.0.0.1:4173', channel: 'chromium', headless: true, trace: 'off' },
  projects: [390, 820, 1440].map((width) => ({
    name: `w${width}`,
    use: { ...devices['Desktop Chrome'], channel: 'chromium', viewport: { width, height: 900 }, isMobile: false, hasTouch: width < 640 },
  })),
  webServer: {
    command: 'npm run preview -- --port 4173 --strictPort --host 127.0.0.1',
    cwd: '../../../../web',
    url: 'http://127.0.0.1:4173',
    reuseExistingServer: true,
    timeout: 120_000,
    stdout: 'ignore',
    stderr: 'pipe',
  },
});
