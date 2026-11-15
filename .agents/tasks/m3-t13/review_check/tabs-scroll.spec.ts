import { expect, test } from '../../../../web/node_modules/@playwright/test/index.mjs';
import { mockApi } from '../../../../web/e2e/mockApi.ts';

for (const path of ['/runs/run-complete', '/runs/run-partial']) {
  test(`seven tabs stay inside their row on ${path}`, async ({ page }) => {
    await mockApi(page);
    await page.goto(path);
    const list = page.getByRole('tablist');
    await list.waitFor();
    expect(await page.getByRole('tab').count()).toBe(7);
    const before = await page.evaluate(() => ({
      sideways: document.documentElement.scrollWidth > window.innerWidth + 1,
      pageX: window.scrollX,
    }));
    expect(before.sideways, 'page scrolls sideways').toBe(false);
    await page.getByRole('tab', { name: 'Overview', exact: true }).focus();
    for (let step = 0; step < 6; step += 1) {
      await page.keyboard.press('ArrowRight');
      const state = await page.evaluate(() => {
        const row = document.querySelector('[role=tablist]') as HTMLElement;
        const tab = document.activeElement as HTMLElement;
        const box = row.getBoundingClientRect();
        const item = tab.getBoundingClientRect();
        return {
          sideways: document.documentElement.scrollWidth > window.innerWidth + 1,
          pageX: window.scrollX,
          inView: item.left >= box.left - 1 && item.right <= box.right + 1,
          label: tab.textContent,
        };
      });
      expect(state.sideways, `sideways after ${state.label}`).toBe(false);
      expect(state.pageX, `page moved after ${state.label}`).toBe(0);
      expect(state.inView, `${state.label} out of view`).toBe(true);
    }
  });
}
