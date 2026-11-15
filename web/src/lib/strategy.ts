import type { components } from '@/api/types.gen';

export type StrategyConstraints = components['schemas']['StrategyConstraints'];
export type ConstraintLimits = components['schemas']['ConstraintLimits'];
export type BudgetLevel = NonNullable<StrategyConstraints['budget_level']>;
export type TechnicalSkill = NonNullable<StrategyConstraints['technical_skill']>;

export const BUDGET_LABELS: Record<BudgetLevel, string> = {
  bootstrapped: 'Bootstrapped',
  small: 'Small budget',
  funded: 'Funded',
};

export const SKILL_LABELS: Record<TechnicalSkill, string> = {
  non_technical: 'Non-technical',
  some: 'Some technical',
  strong: 'Strong technical team',
};

function plain(value: string): string {
  const text = value.replace(/_/g, ' ');
  return text.charAt(0).toUpperCase() + text.slice(1);
}

export function budgetLabel(value: string): string {
  return BUDGET_LABELS[value as BudgetLevel] ?? plain(value);
}

export function skillLabel(value: string): string {
  return SKILL_LABELS[value as TechnicalSkill] ?? plain(value);
}

export function range(min: number, max: number): number[] {
  return Array.from({ length: Math.max(max - min + 1, 0) }, (_, index) => min + index);
}
