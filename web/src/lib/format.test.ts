import { describe, expect, it } from 'vitest';

import { count, dateTime, domainOf, duration } from '@/lib/format';

describe('duration', () => {
  it('shows seconds with one decimal under a minute', () => {
    expect(duration(6.53)).toBe('6.5 s');
    expect(duration(0)).toBe('0.0 s');
  });

  it('switches to minutes and seconds at a minute', () => {
    expect(duration(106)).toBe('1:46');
    expect(duration(60)).toBe('1:00');
  });

  it('shows a dash rather than a number it does not have', () => {
    expect(duration(null)).toBe('\u2014');
    expect(duration(undefined)).toBe('\u2014');
    expect(duration(Number.NaN)).toBe('\u2014');
    expect(duration(-1)).toBe('\u2014');
  });
});

describe('count', () => {
  it('pluralises', () => {
    expect(count(1, 'competitor')).toBe('1 competitor');
    expect(count(3, 'competitor')).toBe('3 competitors');
    expect(count(0, 'competitor')).toBe('0 competitors');
  });
});

describe('domainOf', () => {
  it('drops the scheme and www', () => {
    expect(domainOf('https://www.Example.com/a/b?c=1')).toBe('example.com');
  });

  it('returns an empty string for something that is not a URL', () => {
    expect(domainOf('not a url')).toBe('');
    expect(domainOf(null)).toBe('');
  });
});

describe('dateTime', () => {
  it('shows a dash for a missing or unreadable timestamp', () => {
    expect(dateTime(null)).toBe('\u2014');
    expect(dateTime('not a date')).toBe('\u2014');
  });

  it('formats a real timestamp', () => {
    expect(dateTime('2026-10-29T15:04:00.000Z')).toMatch(/2026/);
  });
});
