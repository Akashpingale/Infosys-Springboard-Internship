/**
 * Keyboard and motion (KIRO_UI_UPGRADE_SPEC.md Sections 6.6 and 6.9).
 *
 * The four interactive patterns the specification names are driven by keyboard only: the result
 * tabs, the source drawer, the industry combobox and the chip input. Then the same screen is loaded
 * with prefers-reduced-motion: reduce, and the page must not animate.
 *
 * These run at one width; the layout does not change what a key does, and the screenshot and
 * accessibility runs already cover all three widths.
 */

import { expect, test } from '@playwright/test';

import { mockApi } from './mockApi';

const RUN = '/runs/run-complete';

/** What currently has focus, as a short description. */
async function focused(page: import('@playwright/test').Page): Promise<string> {
  return page.evaluate(() => {
    const element = document.activeElement;
    if (!element || element === document.body) {
      return 'body';
    }
    const name = (element.getAttribute('aria-label') ?? element.textContent ?? '').trim();
    return `${element.tagName.toLowerCase()}:${name.replace(/\s+/g, ' ').slice(0, 40)}`;
  });
}

test.describe('keyboard', () => {
  test('every control the Tab key reaches shows a focus ring', async ({ page }) => {
    await mockApi(page);
    await page.goto(RUN);
    await page.getByRole('heading', { name: 'Summary' }).waitFor();

    const seen: string[] = [];
    for (let step = 0; step < 12; step += 1) {
      await page.keyboard.press('Tab');
      const outline = await page.evaluate(() => {
        const element = document.activeElement;
        if (!element || element === document.body) {
          return null;
        }
        const style = getComputedStyle(element);
        return { width: style.outlineWidth, style: style.outlineStyle };
      });
      if (!outline) {
        break;
      }
      seen.push(await focused(page));
      expect(outline.style, `step ${step + 1} has no focus ring`).not.toBe('none');
      expect(Number.parseFloat(outline.width), `step ${step + 1} focus ring too thin`).toBeGreaterThanOrEqual(2);
    }

    // The skip link is first, which is what Section 6.9 asks of it.
    expect(seen[0]).toContain('Skip to main content');
    expect(seen.length).toBeGreaterThan(8);
  });

  test('the result tabs move with the arrow keys and only the open one is tabbable', async ({ page }) => {
    await mockApi(page);
    await page.goto(RUN);
    const overview = page.getByRole('tab', { name: 'Overview', exact: true });
    await overview.waitFor();

    await overview.focus();
    await page.keyboard.press('ArrowRight');
    await expect(page.getByRole('tab', { name: 'Market', exact: true })).toHaveAttribute('aria-selected', 'true');

    await page.keyboard.press('ArrowRight');
    await expect(page.getByRole('tab', { name: 'Competitors', exact: true })).toHaveAttribute('aria-selected', 'true');

    await page.keyboard.press('ArrowLeft');
    await expect(page.getByRole('tab', { name: 'Market', exact: true })).toHaveAttribute('aria-selected', 'true');

    // Exactly one tab is in the tab order (the roving tabindex of the tabs pattern).
    const tabbable = await page.evaluate(
      () => document.querySelectorAll('[role=tab][tabindex="0"]').length,
    );
    expect(tabbable).toBe(1);
  });

  test('the drawer opens with Enter, traps focus and closes with Escape', async ({ page }) => {
    await mockApi(page);
    await page.goto(RUN);
    await page.getByRole('heading', { name: 'Summary' }).waitFor();

    const chip = page.getByRole('button', { name: /^Source \d+:/ }).first();
    await chip.focus();
    await page.keyboard.press('Enter');

    const drawer = page.getByRole('dialog');
    await expect(drawer).toBeVisible();

    // Focus is inside the dialog, so Tab cannot wander back to the page behind it.
    await page.keyboard.press('Tab');
    expect(await page.evaluate(() => !!document.activeElement?.closest('dialog'))).toBe(true);

    await page.keyboard.press('Escape');
    await expect(drawer).toBeHidden();
  });

  test('the industry combobox is usable with the keyboard alone', async ({ page }) => {
    await mockApi(page);
    await page.goto('/');
    const combobox = page.getByRole('combobox', { name: /industry/i });
    await combobox.waitFor();

    await combobox.focus();
    await page.keyboard.press('Enter');
    await page.getByRole('option').first().waitFor();

    await page.keyboard.type('fin');
    await page.keyboard.press('ArrowDown');
    await page.keyboard.press('Enter');

    await expect(combobox).toContainText('Finance / FinTech');
  });

  test('the chip input adds and removes a customer with the keyboard alone', async ({ page }) => {
    await mockApi(page);
    await page.goto('/');
    const field = page.getByLabel(/target customers/i);
    await field.waitFor();

    await field.focus();
    await page.keyboard.type('Small business owners');
    await page.keyboard.press('Enter');
    await expect(page.getByText('Small business owners')).toBeVisible();

    await page.keyboard.type('Shopkeepers');
    await page.keyboard.press('Enter');
    await expect(page.getByText('Shopkeepers')).toBeVisible();

    // Backspace on an empty field takes the last chip back off.
    await page.keyboard.press('Backspace');
    await expect(page.getByText('Shopkeepers')).toBeHidden();
    await expect(page.getByText('Small business owners')).toBeVisible();
  });
});

test.describe('reduced motion', () => {
  test('nothing on the page animates when motion is not wanted', async ({ page }) => {
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await mockApi(page);
    await page.goto(RUN);
    await page.getByRole('heading', { name: 'Summary' }).waitFor();

    const moving = await page.evaluate(() =>
      [...document.querySelectorAll('*')].filter((element) => {
        const style = getComputedStyle(element);
        return (
          Number.parseFloat(style.transitionDuration) > 0.05 ||
          Number.parseFloat(style.animationDuration) > 0.05
        );
      }).length,
    );

    expect(moving).toBe(0);
  });

  test('a tab still changes instantly', async ({ page }) => {
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await mockApi(page);
    await page.goto(RUN);
    const market = page.getByRole('tab', { name: 'Market', exact: true });
    await market.click();

    await expect(market).toHaveAttribute('aria-selected', 'true');
    await expect(page.getByRole('navigation', { name: 'Market sections' })).toBeVisible();
  });
});
