/**
 * Screenshots of every screen and state, at 390, 820 and 1440 px (KIRO_UI_UPGRADE_SPEC.md Prompt J).
 *
 * The files land in docs/assets/ui_v2/ as <screen>-<width>.png. The backend is mocked by route
 * interception (mockApi.ts), so the loading, partial, failed, cancelled, empty and offline states
 * can each be photographed without a server and without spending a credit.
 *
 * Each page is also checked for sideways scrolling, which is the failure a narrow screen shows
 * first, and nothing is allowed to ask the backend to start a run.
 */

import { existsSync, mkdirSync } from 'node:fs';
import { join } from 'node:path';

import { expect, test } from '@playwright/test';

import { SHOTS_DIR } from '../playwright.config';
import { mockApi } from './mockApi';
import { SCREENS } from './screens';

const OUT = join(process.cwd(), SHOTS_DIR);

test.beforeAll(() => {
  if (!existsSync(OUT)) {
    mkdirSync(OUT, { recursive: true });
  }
});

for (const screen of SCREENS) {
  test(`${screen.name}`, async ({ page }, testInfo) => {
    const width = testInfo.project.use.viewport?.width ?? 0;
    const asked = await mockApi(page, screen.mock ?? {});

    await page.goto(screen.path);
    if (screen.ready) {
      await page.locator(screen.ready).first().waitFor({ state: 'visible', timeout: 30_000 });
    }
    await screen.after?.(page);

    // The fonts are self-hosted, so this settles quickly; without it text can shift mid-shot.
    await page.evaluate(() => document.fonts.ready.then(() => true));
    await page.waitForTimeout(250);

    await page.screenshot({
      path: join(OUT, `${screen.name}-${width}.png`),
      fullPage: true,
      animations: 'disabled',
    });

    // Section 6.9: a screen that scrolls sideways is broken at that width.
    const sideways = await page.evaluate(
      () => document.documentElement.scrollWidth > window.innerWidth + 1,
    );
    expect(sideways, `${screen.name} scrolls sideways at ${width} px`).toBe(false);

    expect(asked.filter((call) => call === 'POST /api/runs')).toEqual([]);
  });
}
