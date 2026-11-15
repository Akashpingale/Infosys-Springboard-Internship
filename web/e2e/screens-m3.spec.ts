import { existsSync, mkdirSync } from 'node:fs';
import { join } from 'node:path';

import { expect, test, type Page } from '@playwright/test';

import { SHOTS_DIR_M3 } from '../playwright.config';
import { M3_SCREENS, MIN_TARGET, TOUCH_WIDTH, openScreen } from './screensM3';

const OUT = join(process.cwd(), SHOTS_DIR_M3);

test.beforeAll(() => {
  if (!existsSync(OUT)) {
    mkdirSync(OUT, { recursive: true });
  }
});

function smallTargets(page: Page, regions: string[]): Promise<string[]> {
  return page.evaluate(
    ({ regions, min }) => {
      const controls = 'button, a[href], select, summary, input[type=radio], input[type=checkbox], [role=tab]';
      const seen = new Set<Element>();
      const small: string[] = [];
      for (const region of regions) {
        for (const root of document.querySelectorAll(region)) {
          for (const element of root.querySelectorAll(controls)) {
            if (seen.has(element) || element.matches('[aria-label$="Open the source details."]')) {
              continue;
            }
            seen.add(element);
            const choice = element instanceof HTMLInputElement && (element.type === 'radio' || element.type === 'checkbox');
            const target = choice ? (element.closest('label') ?? element) : element;
            const box = target.getBoundingClientRect();
            if (box.width <= 1 || box.height <= 1 || getComputedStyle(element).visibility === 'hidden') {
              continue;
            }
            if (box.width < min - 0.5 || box.height < min - 0.5) {
              const name = (element.getAttribute('aria-label') ?? target.textContent ?? '').replace(/\s+/g, ' ').trim();
              small.push(`${element.tagName.toLowerCase()} "${name.slice(0, 50)}" ${Math.round(box.width)}x${Math.round(box.height)}`);
            }
          }
        }
      }
      return small;
    },
    { regions, min: MIN_TARGET },
  );
}

for (const screen of M3_SCREENS) {
  test(`${screen.name}`, async ({ page }, testInfo) => {
    const width = testInfo.project.use.viewport?.width ?? 0;
    const asked = await openScreen(page, screen);
    await page.waitForTimeout(250);

    const path = join(OUT, `${screen.name}-${width}.png`);
    if (screen.shot) {
      await page.locator(screen.shot).screenshot({ path, animations: 'disabled' });
    } else {
      await page.screenshot({ path, fullPage: true, animations: 'disabled' });
    }

    const sideways = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
    expect(sideways, `${screen.name} scrolls sideways at ${width} px`).toBe(false);

    if (width < TOUCH_WIDTH && screen.targets) {
      expect(await smallTargets(page, screen.targets), `${screen.name}: targets under ${MIN_TARGET} px`).toEqual([]);
    }

    expect(asked.filter((call) => call === 'POST /api/runs')).toEqual([]);
    expect(asked.filter((call) => call.startsWith('POST ') && call.endsWith('/strategy'))).toEqual([]);
  });
}
