import { describe, expect, it } from 'vitest';

import {
  basisCounts,
  buildSourceIndex,
  claimsCiting,
  collectClaims,
  competitorCounts,
  marketSizeSummary,
  resolveSources,
  sourceKey,
} from '@/lib/results';
import { COMPETITOR_S1_URL, COMPLETE_RESULT, MARKET_S1_URL } from '@/test/runFixtures';

describe('source index', () => {
  it('keeps the two analyses apart, because each numbers its own evidence', () => {
    const index = buildSourceIndex(COMPLETE_RESULT);

    const marketS1 = index.get(sourceKey('market', 'S1'));
    const competitorS1 = index.get(sourceKey('competitors', 'S1'));

    expect(marketS1?.url).toBe(MARKET_S1_URL);
    expect(competitorS1?.url).toBe(COMPETITOR_S1_URL);
    expect(marketS1?.number).not.toBe(competitorS1?.number);
  });

  it('numbers the sources from one upward, so no evidence id is shown to the reader', () => {
    const numbers = [...buildSourceIndex(COMPLETE_RESULT).values()].map((source) => source.number);
    expect(numbers).toEqual([1, 2, 3, 4]);
  });

  it('marks the search summary, which has no page behind it', () => {
    const summary = buildSourceIndex(COMPLETE_RESULT).get(sourceKey('market', 'S0'));
    expect(summary?.isSummary).toBe(true);
    expect(summary?.url).toBe('');
  });

  it('reads the domain of each source', () => {
    expect(buildSourceIndex(COMPLETE_RESULT).get(sourceKey('market', 'S1'))?.domain).toBe('reports.example');
  });
});

describe('resolving a claim to its sources', () => {
  const index = buildSourceIndex(COMPLETE_RESULT);

  it('resolves within the analysis the claim belongs to', () => {
    expect(resolveSources(index, 'market', ['S1'])[0]?.url).toBe(MARKET_S1_URL);
    expect(resolveSources(index, 'competitors', ['S1'])[0]?.url).toBe(COMPETITOR_S1_URL);
  });

  it('ignores an id the result does not list, rather than inventing a source', () => {
    expect(resolveSources(index, 'market', ['S99'])).toEqual([]);
  });

  it('returns nothing when the claim names no analysis', () => {
    expect(resolveSources(index, null, ['S1'])).toEqual([]);
    expect(resolveSources(index, 'market', undefined)).toEqual([]);
  });
});

describe('claims', () => {
  const claims = collectClaims(COMPLETE_RESULT);

  it('finds the labelled findings in both analyses', () => {
    expect(claims.length).toBeGreaterThan(5);
    expect(claims.some((claim) => claim.analysis === 'market')).toBe(true);
    expect(claims.some((claim) => claim.analysis === 'competitors')).toBe(true);
  });

  it('keeps each claim text exactly as the agents left it', () => {
    const demand = claims.find((claim) => claim.text.startsWith('Most small farmers'));
    expect(demand?.basis).toBe('sourced');
    expect(demand?.sourceKeys).toEqual([sourceKey('market', 'S1')]);
  });

  it('says where a claim sits, for the drawer', () => {
    expect(claims.find((claim) => claim.text === 'Crops lost to late diagnosis')?.where).toBe('Pain points');
  });

  it('counts the bases in the fixed order of the specification', () => {
    const counts = basisCounts(claims);
    expect(counts.map((entry) => entry.basis)).toEqual([
      'sourced',
      'ai_interpretation',
      'user_provided',
      'assumption',
    ]);
    expect(counts.every((entry) => entry.count >= 0)).toBe(true);
    expect(counts.reduce((sum, entry) => sum + entry.count, 0)).toBe(claims.length);
  });

  it('lists the claims that cite one source', () => {
    const citing = claimsCiting(claims, sourceKey('market', 'S1'));
    expect(citing.length).toBeGreaterThan(1);
    expect(citing.every((claim) => claim.analysis === 'market')).toBe(true);
  });

  it('finds nothing for a source nothing rests on', () => {
    expect(claimsCiting(claims, sourceKey('market', 'S42'))).toEqual([]);
  });
});

describe('market size', () => {
  it('reports the figure a source confirmed and names what is missing', () => {
    const summary = marketSizeSummary(COMPLETE_RESULT);
    expect(summary.sourced).toEqual({
      label: 'TAM',
      value: 'USD 1.8 billion',
      note: 'AI crop disease detection market, 2025',
    });
    expect(summary.unavailable).toEqual(['SAM', 'SOM']);
    expect(summary.estimated).toEqual([]);
  });

  it('claims nothing when there is no market analysis', () => {
    const summary = marketSizeSummary({ ...COMPLETE_RESULT, market: null });
    expect(summary.sourced).toBeNull();
    expect(summary.unavailable).toEqual([]);
  });
});

describe('competitor counts', () => {
  it('counts by type from the result', () => {
    expect(competitorCounts(COMPLETE_RESULT)).toEqual({ total: 2, direct: 1, indirect: 1, emerging: 0 });
  });

  it('is all zero without a competitor analysis', () => {
    expect(competitorCounts({ ...COMPLETE_RESULT, competitors: null }).total).toBe(0);
  });
});
