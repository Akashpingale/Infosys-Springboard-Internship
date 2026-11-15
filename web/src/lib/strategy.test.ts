import { describe, expect, it } from 'vitest';

import { BUDGET_LABELS, SKILL_LABELS, budgetLabel, range, skillLabel } from '@/lib/strategy';
import { META_WITH_STRATEGY, SYNTHETIC_STRATEGY_RESULT } from '@/test/strategyHandlers';

describe('strategy labels', () => {
  it('names every budget level and skill the backend offers in plain words', () => {
    const limits = META_WITH_STRATEGY.strategy!.constraints;
    expect(limits.budget_levels.map(budgetLabel)).toEqual(['Bootstrapped', 'Small budget', 'Funded']);
    expect(limits.technical_skills.map(skillLabel)).toEqual([
      'Non-technical',
      'Some technical',
      'Strong technical team',
    ]);
    expect(Object.keys(BUDGET_LABELS)).toEqual(limits.budget_levels);
    expect(Object.keys(SKILL_LABELS)).toEqual(limits.technical_skills);
  });

  it('never shows a raw code for a choice it does not know', () => {
    expect(budgetLabel('venture_backed')).toBe('Venture backed');
    expect(skillLabel('expert')).toBe('Expert');
  });

  it('lists every whole number between the limits', () => {
    expect(range(1, 4)).toEqual([1, 2, 3, 4]);
    expect(range(3, 3)).toEqual([3]);
    expect(range(5, 4)).toEqual([]);
  });
});

describe('synthetic strategy fixture', () => {
  it('is a complete result with all three strategy parts, and its constraints use the offered choices', () => {
    expect(SYNTHETIC_STRATEGY_RESULT.status).toBe('complete');
    expect(SYNTHETIC_STRATEGY_RESULT.swot).toBeTruthy();
    expect(SYNTHETIC_STRATEGY_RESULT.mvp).toBeTruthy();
    expect(SYNTHETIC_STRATEGY_RESULT.gtm).toBeTruthy();
    const limits = META_WITH_STRATEGY.strategy!.constraints;
    expect(limits.budget_levels).toContain(SYNTHETIC_STRATEGY_RESULT.constraints?.budget_level);
  });
});
