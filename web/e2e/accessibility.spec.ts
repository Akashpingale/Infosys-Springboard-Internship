/**
 * Accessibility checks (KIRO_UI_UPGRADE_SPEC.md Sections 6.9 and Prompt J).
 *
 * axe-core runs on every screen in the list, at all three widths, and any violation it rates
 * serious or critical fails the test. Moderate and minor findings are reported in the output but do
 * not fail, which is the floor the specification sets.
 *
 * The rules cover what Section 6.9 asks for: contrast, names on controls, form labels, heading
 * order and ARIA correctness.
 */

import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';

import { mockApi } from './mockApi';
import { SCREENS } from './screens';

const BLOCKING = new Set(['serious', 'critical']);

for (const screen of SCREENS) {
  const run = screen.skipAxe ? test.skip : test;
  run(`${screen.name} has no serious or critical violation`, async ({ page }) => {
    await mockApi(page, screen.mock ?? {});

    await page.goto(screen.path);
    if (screen.ready) {
      // Generous: axe analysing the screen before this one can take fifteen seconds of CPU on its
      // own, and the wait should not be the thing that fails when the machine is busy.
      await page.locator(screen.ready).first().waitFor({ state: 'visible', timeout: 30_000 });
    }
    await screen.after?.(page);
    await page.evaluate(() => document.fonts.ready.then(() => true));

    const results = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
      .analyze();

    const blocking = results.violations.filter((violation) => BLOCKING.has(violation.impact ?? ''));
    const lesser = results.violations.filter((violation) => !BLOCKING.has(violation.impact ?? ''));

    if (lesser.length > 0) {
      console.log(
        `  ${screen.name}: ${lesser.length} moderate or minor: ` +
          lesser.map((violation) => `${violation.id} (${violation.nodes.length})`).join(', '),
      );
    }

    expect(
      blocking.map((violation) => ({
        id: violation.id,
        impact: violation.impact,
        help: violation.help,
        nodes: violation.nodes.map((node) => node.target.join(' ')),
      })),
      `${screen.name}: serious or critical accessibility violations`,
    ).toEqual([]);
  });
}
