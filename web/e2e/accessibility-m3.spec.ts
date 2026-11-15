import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';

import { M3_SCREENS, openScreen } from './screensM3';

const BLOCKING = new Set(['serious', 'critical']);

for (const screen of M3_SCREENS) {
  const run = screen.skipAxe ? test.skip : test;
  run(`${screen.name} has no serious or critical violation`, async ({ page }) => {
    await openScreen(page, screen);

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
