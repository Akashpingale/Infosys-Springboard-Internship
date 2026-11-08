/**
 * The design tokens, and the one way they can be used wrongly (KIRO_UI_UPGRADE_SPEC.md Section 6.2).
 *
 * Every colour in this interface is a CSS variable holding a whole colour, such as `#38bdf8`.
 * Tailwind can only apply an opacity modifier to a variable that holds bare channel numbers, so a
 * class like `bg-primary/75` or `border-sourced/40` produces no rule whatsoever: the element is
 * simply never painted, with no warning at build time and nothing in the console.
 *
 * That silently hid three of the four stage-timing segments, four chip borders and two panel fills.
 * These tests read the source and the token file, so the mistake cannot come back unnoticed.
 */

import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';

import { describe, expect, it } from 'vitest';

const SRC = join(process.cwd(), 'src');
const TOKENS = join(SRC, 'styles', 'tokens.css');

/** Every colour name tailwind.config.js maps onto a CSS variable. */
const TOKEN_COLOURS = [
  'canvas',
  'surface',
  'raised',
  'raised-soft',
  'line',
  'line-strong',
  'content',
  'primary',
  'ring',
  'success',
  'warning',
  'danger',
  'info',
  'step',
  'sourced',
  'interpretation',
  'provided',
  'assumption',
];

const UTILITIES = ['bg', 'border', 'text', 'divide', 'ring', 'fill', 'stroke', 'from', 'via', 'to'];

/** For example `bg-primary/75`, `border-sourced-border/40`, `even:bg-raised/40`. */
const FORBIDDEN = new RegExp(
  `\\b(?:${UTILITIES.join('|')})-(?:${TOKEN_COLOURS.join('|')})(?:-[a-z0-9]+)*/\\d`,
  'g',
);

/**
 * Code with its comments removed.
 *
 * The rule is about classes the browser is given, and several files explain the rule in prose by
 * quoting the very class they must not use. A line starting with `//` or `*` and anything between
 * `/*` and its close are dropped; a `//` inside a string, such as a URL, is left alone.
 */
function stripComments(source: string): string {
  return source
    .replace(/\/\*[\s\S]*?\*\//g, ' ')
    .split('\n')
    .filter((line) => !/^\s*(\/\/|\*)/.test(line))
    .join('\n');
}

function sourceFiles(directory: string = SRC): string[] {
  const found: string[] = [];
  for (const entry of readdirSync(directory)) {
    const path = join(directory, entry);
    if (statSync(path).isDirectory()) {
      found.push(...sourceFiles(path));
    } else if (/\.tsx?$/.test(entry) && entry !== 'tokens.test.ts') {
      found.push(path);
    }
  }
  return found;
}

describe('design tokens', () => {
  it('is never asked for an opacity it cannot give', () => {
    const offenders: string[] = [];
    for (const file of sourceFiles()) {
      for (const match of stripComments(readFileSync(file, 'utf8')).matchAll(FORBIDDEN)) {
        offenders.push(`${file.slice(SRC.length + 1)}: ${match[0]}`);
      }
    }

    expect(offenders).toEqual([]);
  });

  it('scans enough files to be meaningful, and still catches an offender', () => {
    // A guard that would quietly pass if the walk broke, or if comment-stripping ate the code,
    // is worse than no guard at all.
    expect(sourceFiles().length).toBeGreaterThan(40);

    const pattern = new RegExp(FORBIDDEN.source);
    expect(stripComments('const x = cn("border-sourced/40");')).toMatch(pattern);
    expect(stripComments('/* bg-primary/75 is wrong */ const y = 1;')).not.toMatch(pattern);
    // A line holding a URL keeps its code: only comment lines go.
    expect(stripComments('const url = "https://example.com/page";')).toContain('example.com');
  });

  it('defines every colour it promises, in both themes', () => {
    const css = readFileSync(TOKENS, 'utf8');
    const [, dark = '', light = ''] = css.split(/\[data-theme='(?:dark|light)'\]/);

    const names = [...css.matchAll(/^\s*(--[a-z0-9-]+):/gm)].map((match) => match[1]);
    expect(new Set(names).size).toBeGreaterThan(30);

    // The four basis edges and the soft fill are the ones this prompt added.
    for (const token of [
      '--raised-soft',
      '--basis-sourced-border',
      '--basis-interpretation-border',
      '--basis-provided-border',
      '--basis-assumption-border',
      '--chart-step-1',
      '--chart-step-4',
    ]) {
      expect(dark, `${token} missing from the dark theme`).toContain(`${token}:`);
      expect(light, `${token} missing from the light theme`).toContain(`${token}:`);
    }
  });
});
