import { describe, expect, it } from 'vitest';

import {
  ideaFormSchema,
  joinCustomers,
  reviewFormSchema,
  splitCustomers,
} from '@/features/new-validation/schema';
import { META, VALID_IDEA } from '@/test/fixtures';

const schema = ideaFormSchema(META.limits);
const review = reviewFormSchema(META.limits);

const VALID = {
  idea_description: VALID_IDEA,
  industry: 'Agriculture / AgriTech',
  target_customers: ['Small farmers'],
  relevant_details: '',
};

function messageFor(values: Partial<typeof VALID>, field: keyof typeof VALID): string | undefined {
  const parsed = schema.safeParse({ ...VALID, ...values });
  if (parsed.success) {
    return undefined;
  }
  return parsed.error.issues.find((issue) => issue.path[0] === field)?.message;
}

describe('idea form rules', () => {
  it('accepts a complete submission', () => {
    expect(schema.safeParse(VALID).success).toBe(true);
  });

  it('builds its messages from the limits the backend reported', () => {
    expect(messageFor({ idea_description: 'Too short to be an idea' }, 'idea_description')).toBe(
      'Describe your idea in at least 30 characters.',
    );
    expect(messageFor({ idea_description: 'x'.repeat(2001) }, 'idea_description')).toBe(
      'Keep the idea to 2000 characters or fewer.',
    );
  });

  it('asks for the minimum number of words, not just characters', () => {
    const long = 'Supercalifragilisticexpialidociousandthensomemorelettersdefinitely';
    expect(long.length).toBeGreaterThan(30);
    expect(messageFor({ idea_description: long }, 'idea_description')).toBe(
      'Describe your idea in at least 3 words.',
    );
  });

  it('asks for an industry and at least one customer', () => {
    expect(messageFor({ industry: '' }, 'industry')).toBe('Choose an industry, or type your own.');
    expect(messageFor({ target_customers: [] }, 'target_customers')).toBe('Add at least one target customer.');
  });

  it('measures the customers against the joined length the backend receives', () => {
    const many = ['x'.repeat(150), 'y'.repeat(150), 'z'.repeat(150)];
    expect(joinCustomers(many).length).toBeGreaterThan(300);
    expect(messageFor({ target_customers: many }, 'target_customers')).toBe(
      'Keep the customers to 300 characters or fewer in total.',
    );
  });

  it('leaves the optional context optional, but holds it to its limit', () => {
    expect(schema.safeParse({ ...VALID, relevant_details: '' }).success).toBe(true);
    expect(messageFor({ relevant_details: 'x'.repeat(1501) }, 'relevant_details')).toBe(
      'Keep the extra context to 1500 characters or fewer.',
    );
  });

  it('trims what it reads, so spaces alone are not an answer', () => {
    expect(messageFor({ industry: '   ' }, 'industry')).toBe('Choose an industry, or type your own.');
  });
});

describe('customer chips', () => {
  it('joins and splits around the same separator', () => {
    expect(joinCustomers(['Small farmers', 'Cooperatives'])).toBe('Small farmers, Cooperatives');
    expect(splitCustomers('Small farmers, Cooperatives')).toEqual(['Small farmers', 'Cooperatives']);
  });

  it('drops empty entries rather than sending a stray separator', () => {
    expect(joinCustomers(['Small farmers', '   ', ''])).toBe('Small farmers');
    expect(splitCustomers('Small farmers,,; ')).toEqual(['Small farmers']);
  });
});

describe('review step rules', () => {
  const VALID_REVIEW = {
    idea_title: 'CropScan',
    problem: 'Crops are lost.',
    solution: 'An app diagnoses them.',
    industry: 'Agriculture / AgriTech',
    target_customers: ['Small farmers'],
    key_features: ['One', 'Two', 'Three'],
  };

  it('accepts the extracted idea as it came back', () => {
    expect(review.safeParse(VALID_REVIEW).success).toBe(true);
  });

  it('holds the feature count to the range the extracted idea allows', () => {
    const tooFew = review.safeParse({ ...VALID_REVIEW, key_features: ['One', 'Two'] });
    expect(tooFew.success).toBe(false);
    expect(tooFew.success === false && tooFew.error.issues[0]?.message).toBe('List at least 3 key features.');

    const tooMany = review.safeParse({
      ...VALID_REVIEW,
      key_features: ['1', '2', '3', '4', '5', '6', '7'],
    });
    expect(tooMany.success).toBe(false);
    expect(tooMany.success === false && tooMany.error.issues[0]?.message).toBe('List at most 6 key features.');
  });

  it('keeps the title within the length the backend accepts', () => {
    const parsed = review.safeParse({ ...VALID_REVIEW, idea_title: 'x'.repeat(81) });
    expect(parsed.success).toBe(false);
    expect(parsed.success === false && parsed.error.issues[0]?.message).toBe(
      'Keep the title to 80 characters or fewer.',
    );
  });

  it('will not let a required field be emptied', () => {
    for (const field of ['idea_title', 'problem', 'solution', 'industry'] as const) {
      expect(review.safeParse({ ...VALID_REVIEW, [field]: '  ' }).success).toBe(false);
    }
  });
});
