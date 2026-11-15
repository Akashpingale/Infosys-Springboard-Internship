import { expect, test, type Page } from '@playwright/test';

import { conversationThread, mockApi } from './mockApi';
import { SCREENS } from './screens';
import { M3_SCREENS, openScreen } from './screensM3';

const RUN = '/runs/run-strategy';
const CHAT = '/api/runs/run-strategy/chat';
const SEVEN = ['Overview', 'Market', 'Competitors', 'Strategy', 'Advisor', 'Sources', 'Run details'];

async function expectRing(page: Page, what: string): Promise<void> {
  const outline = await page.evaluate(() => {
    const element = document.activeElement;
    if (!element || element === document.body) {
      return null;
    }
    const style = getComputedStyle(element);
    return { style: style.outlineStyle, width: Number.parseFloat(style.outlineWidth) };
  });
  expect(outline, `${what} has focus`).not.toBeNull();
  expect(outline?.style, `${what} has no focus ring`).not.toBe('none');
  expect(outline?.width ?? 0, `${what} focus ring too thin`).toBeGreaterThanOrEqual(2);
}

function sideways(page: Page): Promise<boolean> {
  return page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
}

function tabInView(page: Page, label: string): Promise<boolean> {
  return page.evaluate((name) => {
    const list = document.querySelector('[role=tablist]');
    const tab = [...document.querySelectorAll('[role=tab]')].find((entry) => entry.textContent?.trim() === name);
    if (!list || !tab) {
      return false;
    }
    const row = list.getBoundingClientRect();
    const box = tab.getBoundingClientRect();
    return box.left >= row.left - 1 && box.right <= row.right + 1;
  }, label);
}

async function openAdvisor(page: Page): Promise<void> {
  await page.getByRole('tab', { name: 'Advisor', exact: true }).click();
  await page.getByRole('textbox', { name: 'Your question' }).waitFor();
}

function chatPost(page: Page) {
  return page.waitForRequest((request) => request.method() === 'POST' && new URL(request.url()).pathname === CHAT);
}

test.describe('keyboard on the Milestone 3 screens', () => {
  test('the seven result tabs cycle with the arrow keys, stay in view and never move the page', async ({ page }) => {
    await mockApi(page);
    await page.goto(RUN);
    const overview = page.getByRole('tab', { name: 'Overview', exact: true });
    await overview.waitFor();

    expect((await page.getByRole('tab').allTextContents()).map((label) => label.trim())).toEqual(SEVEN);

    await overview.focus();
    await expectRing(page, 'Overview tab');
    for (const label of [...SEVEN.slice(1), SEVEN[0] ?? '']) {
      await page.keyboard.press('ArrowRight');
      const tab = page.getByRole('tab', { name: label, exact: true });
      await expect(tab).toHaveAttribute('aria-selected', 'true');
      await expect(tab).toBeFocused();
      expect(await tabInView(page, label), `${label} tab is out of view`).toBe(true);
      expect(await sideways(page), `${label} tab moved the page sideways`).toBe(false);
      expect(await page.evaluate(() => document.querySelectorAll('[role=tab][tabindex="0"]').length)).toBe(1);
    }

    await page.keyboard.press('ArrowLeft');
    await expect(page.getByRole('tab', { name: 'Run details', exact: true })).toHaveAttribute('aria-selected', 'true');
    expect(await tabInView(page, 'Run details')).toBe(true);
  });

  test('the constraints panel opens and fills with the keyboard alone', async ({ page }) => {
    const asked = await mockApi(page);
    await page.goto('/');
    await page.getByRole('heading', { name: 'Check your startup idea' }).waitFor();
    await SCREENS.find((screen) => screen.name === 'review-step')?.after?.(page);

    const strategySwitch = page.getByRole('switch', { name: 'Include strategy' });
    await expect(strategySwitch).toBeChecked();
    const summary = page.locator('summary', { hasText: 'Resources and goals (optional)' });
    await strategySwitch.focus();
    await page.keyboard.press('Tab');
    await expect(summary).toBeFocused();
    await expectRing(page, 'Resources and goals summary');
    await page.keyboard.press('Enter');
    const team = page.getByLabel('Team size');
    await expect(team).toBeVisible();

    await page.keyboard.press('Tab');
    await expect(team).toBeFocused();
    await expectRing(page, 'Team size');
    await page.keyboard.press('ArrowDown');
    await page.keyboard.press('ArrowDown');
    await expect(team).toHaveValue('2');

    await page.keyboard.press('Tab');
    const months = page.getByLabel('Months to first release');
    await expect(months).toBeFocused();
    await page.keyboard.press('ArrowDown');
    await page.keyboard.press('ArrowDown');
    await page.keyboard.press('ArrowDown');
    await expect(months).toHaveValue('3');

    await page.keyboard.press('Tab');
    const bootstrapped = page.getByRole('radio', { name: 'Bootstrapped' });
    await expect(bootstrapped).toBeFocused();
    await expectRing(page, 'Budget level');
    await page.keyboard.press('Space');
    await expect(bootstrapped).toBeChecked();
    await page.keyboard.press('ArrowRight');
    await expect(page.getByRole('radio', { name: 'Small budget' })).toBeChecked();

    await page.keyboard.press('Tab');
    const nonTechnical = page.getByRole('radio', { name: 'Non-technical' });
    await expect(nonTechnical).toBeFocused();
    await page.keyboard.press('Space');
    await expect(nonTechnical).toBeChecked();

    await page.keyboard.press('Tab');
    const region = page.getByLabel('Launch region');
    await expect(region).toBeFocused();
    await expectRing(page, 'Launch region');
    await page.keyboard.type('Pune');
    await expect(region).toHaveValue('Pune');
    await expect(page.getByText('4 / 60')).toBeVisible();

    await summary.focus();
    await page.keyboard.press('Enter');
    await expect(team).toBeHidden();
    expect(await sideways(page)).toBe(false);
    expect(asked.filter((call) => call === 'POST /api/runs')).toEqual([]);
  });

  test('the composer: Shift+Enter starts a line, Enter sends, the reply is announced and focus stays', async ({ page }) => {
    await mockApi(page);
    await page.goto(RUN);
    await openAdvisor(page);

    const box = page.getByRole('textbox', { name: 'Your question' });
    await box.focus();
    await expectRing(page, 'Composer');
    await page.keyboard.type('Which risk matters most?');
    await page.keyboard.press('Shift+Enter');
    await page.keyboard.type('And why?');
    await expect(box).toHaveValue('Which risk matters most?\nAnd why?');

    const sent = chatPost(page);
    await page.keyboard.press('Enter');
    expect(JSON.parse((await sent).postData() ?? '{}')).toEqual({ message: 'Which risk matters most?\nAnd why?' });

    await expect(page.locator('[aria-live="polite"]', { hasText: 'Advisor replied.' })).toHaveCount(1);
    await expect(page.getByRole('list', { name: 'Conversation' })).toContainText('The register rates');
    await expect(box).toBeFocused();
    await expect(box).toHaveValue('');
  });

  test('a suggested question is reached with Shift+Tab and sent with Enter', async ({ page }) => {
    await mockApi(page);
    await page.goto(RUN);
    await openAdvisor(page);

    const suggestions = page.getByRole('list', { name: 'Suggested questions' }).getByRole('button');
    const last = (await suggestions.allTextContents()).map((text) => text.trim()).at(-1) ?? '';
    expect(last).not.toBe('');

    await page.getByRole('textbox', { name: 'Your question' }).focus();
    await page.keyboard.press('Shift+Tab');
    await expect(suggestions.last()).toBeFocused();
    await expectRing(page, 'Suggested question');

    const sent = chatPost(page);
    await page.keyboard.press('Enter');
    expect(JSON.parse((await sent).postData() ?? '{}')).toEqual({ message: last });
    await expect(page.locator('[aria-live="polite"]', { hasText: 'Advisor replied.' })).toHaveCount(1);
  });

  test('the clear dialog opens on Keep it, keeps focus inside, closes with Escape and clears with Enter', async ({ page }) => {
    const asked = await mockApi(page, { thread: conversationThread() });
    await page.goto(RUN);
    await openAdvisor(page);

    const clear = page.getByRole('button', { name: 'Clear conversation' });
    await clear.focus();
    await page.keyboard.press('Enter');
    const dialog = page.getByRole('dialog', { name: 'Clear this conversation?' });
    await expect(dialog).toBeVisible();
    await expect(dialog.getByRole('button', { name: 'Keep it' })).toBeFocused();
    await expectRing(page, 'Keep it');

    await page.keyboard.press('Shift+Tab');
    expect(await page.evaluate(() => !!document.activeElement?.closest('dialog'))).toBe(true);
    await page.keyboard.press('Escape');
    await expect(dialog).toBeHidden();
    expect(asked.filter((call) => call === `DELETE ${CHAT}`)).toEqual([]);

    await clear.focus();
    await page.keyboard.press('Enter');
    await expect(dialog.getByRole('button', { name: 'Keep it' })).toBeFocused();
    await page.keyboard.press('Shift+Tab');
    await expect(dialog.getByRole('button', { name: 'Clear it' })).toBeFocused();
    const removed = page.waitForRequest(
      (request) => request.method() === 'DELETE' && new URL(request.url()).pathname === CHAT,
    );
    await page.keyboard.press('Enter');
    await removed;
    await expect(dialog).toBeHidden();
  });

  test('the regenerate confirm opens on Keep it and Escape sends nothing', async ({ page }) => {
    const asked = await mockApi(page);
    await page.goto(RUN);
    await page.getByRole('tab', { name: 'Strategy', exact: true }).click();

    const change = page.getByRole('button', { name: 'Change resources and regenerate' });
    await change.focus();
    await page.keyboard.press('Enter');
    await expect(change).toHaveAttribute('aria-expanded', 'true');

    const submit = page.getByRole('button', { name: 'Regenerate strategy' });
    await submit.focus();
    await expectRing(page, 'Regenerate strategy');
    await page.keyboard.press('Enter');
    const dialog = page.getByRole('dialog', { name: 'Replace the whole strategy?' });
    await expect(dialog).toBeVisible();
    await expect(dialog.getByRole('button', { name: 'Keep it' })).toBeFocused();

    await page.keyboard.press('Escape');
    await expect(dialog).toBeHidden();
    expect(asked.filter((call) => call.startsWith('POST ') && call.endsWith('/strategy'))).toEqual([]);
  });
});

test.describe('reduced motion on the Milestone 3 screens', () => {
  for (const screen of M3_SCREENS) {
    test(`${screen.name} does not animate`, async ({ page }) => {
      await page.emulateMedia({ reducedMotion: 'reduce' });
      await openScreen(page, screen);

      const moving = await page.evaluate(
        () =>
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
  }
});
