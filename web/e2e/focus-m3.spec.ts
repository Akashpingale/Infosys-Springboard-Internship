import { expect, test, type Page } from '@playwright/test';

import { M3_SCREENS, openScreen } from './screensM3';

const TABBABLE =
  'a[href], button:not([disabled]), select:not([disabled]), textarea:not([disabled]), input:not([disabled]):not([type=hidden]), summary, [tabindex]';
const MAX_STOPS = 500;

interface Stop {
  name: string;
  style: string;
  width: number;
}

function startWalk(page: Page, regions: string[]): Promise<string[]> {
  return page.evaluate(
    ({ regions, selector }) => {
      const folded = (element: Element): boolean => {
        let closed = element.closest('details:not([open])');
        while (closed) {
          if (!closed.querySelector(':scope > summary')?.contains(element)) {
            return true;
          }
          closed = closed.parentElement?.closest('details:not([open])') ?? null;
        }
        return false;
      };
      const seen = new Set<Element>();
      const groups = new Set<string>();
      const stops: HTMLElement[] = [];
      for (const region of regions) {
        for (const root of document.querySelectorAll(region)) {
          for (const element of root.querySelectorAll<HTMLElement>(selector)) {
            if (
              seen.has(element) ||
              element.tabIndex < 0 ||
              element.getClientRects().length === 0 ||
              getComputedStyle(element).visibility === 'hidden' ||
              folded(element)
            ) {
              continue;
            }
            seen.add(element);
            if (element instanceof HTMLInputElement && element.type === 'radio' && element.name) {
              const checked = document.querySelector(`input[type=radio][name="${CSS.escape(element.name)}"]:checked`);
              if (groups.has(element.name) || (checked && checked !== element)) {
                continue;
              }
              groups.add(element.name);
            }
            stops.push(element);
          }
        }
      }
      stops[0]?.focus();
      return stops.map((element) => {
        const name = (element.getAttribute('aria-label') ?? element.textContent ?? '').replace(/\s+/g, ' ').trim();
        return `${element.tagName.toLowerCase()} "${name.slice(0, 50)}"`;
      });
    },
    { regions, selector: TABBABLE },
  );
}

function focused(page: Page, regions: string[]): Promise<Stop | null> {
  return page.evaluate((regions) => {
    const element = document.activeElement;
    if (!element || element === document.body || !regions.some((region) => element.closest(region))) {
      return null;
    }
    const style = getComputedStyle(element);
    const name = (element.getAttribute('aria-label') ?? element.textContent ?? '').replace(/\s+/g, ' ').trim();
    return {
      name: `${element.tagName.toLowerCase()} "${name.slice(0, 50)}"`,
      style: style.outlineStyle,
      width: Number.parseFloat(style.outlineWidth),
    };
  }, regions);
}

for (const screen of M3_SCREENS) {
  test(`${screen.name}: every control the Tab key reaches shows a focus ring`, async ({ page }) => {
    const regions = screen.targets ?? ['main'];
    await openScreen(page, screen);

    const expected = await startWalk(page, regions);
    expect(expected.length, `${screen.name} has no control to reach`).toBeGreaterThan(0);
    await page.keyboard.press('Shift+Tab');
    await page.keyboard.press('Tab');

    const reached: string[] = [];
    let stop = await focused(page, regions);
    while (stop && reached.length < MAX_STOPS) {
      reached.push(stop.name);
      expect(stop.style, `${screen.name}: ${stop.name} has no focus ring`).not.toBe('none');
      expect(stop.width, `${screen.name}: ${stop.name} focus ring too thin`).toBeGreaterThanOrEqual(2);
      await page.keyboard.press('Tab');
      stop = await focused(page, regions);
    }

    expect(reached.length, `${screen.name}: the Tab key never left the screen`).toBeLessThan(MAX_STOPS);
    let next = 0;
    for (const name of reached) {
      if (name === expected[next]) {
        next += 1;
      }
    }
    expect(expected.slice(next), `${screen.name}: controls the Tab key did not reach`).toEqual([]);
    console.log(
      `  ${screen.name}: ${reached.length} Tab stops for ${expected.length} controls, each with a focus ring`,
    );
  });
}
