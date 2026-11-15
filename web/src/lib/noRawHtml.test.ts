import { readFileSync, readdirSync, statSync } from 'node:fs';
import { basename, join } from 'node:path';

import { describe, expect, it } from 'vitest';

const SRC = join(process.cwd(), 'src');
const FORBIDDEN = new RegExp(['dangerously', 'Set', 'Inner', 'HTML'].join(''), 'g');

function sourceFiles(directory: string = SRC): string[] {
  const found: string[] = [];
  for (const entry of readdirSync(directory)) {
    const path = join(directory, entry);
    if (statSync(path).isDirectory()) {
      found.push(...sourceFiles(path));
    } else if (/\.(tsx?|jsx?)$/.test(entry)) {
      found.push(path);
    }
  }
  return found;
}

describe('rendering text as text', () => {
  it('never hands raw HTML to React anywhere in the source', () => {
    const offenders: string[] = [];
    for (const file of sourceFiles()) {
      if (FORBIDDEN.test(readFileSync(file, 'utf8'))) {
        offenders.push(file.slice(SRC.length + 1));
      }
      FORBIDDEN.lastIndex = 0;
    }

    expect(offenders).toEqual([]);
  });

  it('walks enough files to mean something, including the Advisor, and still catches an offender', () => {
    const files = sourceFiles();
    expect(files.length).toBeGreaterThan(60);
    expect(files.map((file) => basename(file))).toEqual(expect.arrayContaining(['AdvisorTab.tsx', 'ChatMessage.tsx']));

    const sample = `<p ${['dangerously', 'SetInnerHTML'].join('')}={{ __html: text }} />`;
    expect(new RegExp(FORBIDDEN.source).test(sample)).toBe(true);
    expect(new RegExp(FORBIDDEN.source).test('<p>{text}</p>')).toBe(false);
  });
});
