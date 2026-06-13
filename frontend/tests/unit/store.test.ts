import { beforeEach, describe, expect, test } from 'vitest';
import { useAppStore } from '../../src/lib/store';

describe('portfolio store', () => {
  beforeEach(() => {
    useAppStore.setState({
      portfolio: {
        schema_version: 3,
        total_capital: 100000,
        holdings: [],
        created_at: '2026-06-11T00:00:00Z',
        updated_at: '2026-06-11T00:00:00Z',
        local_storage_notice_acknowledged: true,
      },
      watchlist: [],
    });
  });

  test('addHolding merges an existing ticker with weighted average cost', () => {
    const { addHolding } = useAppStore.getState();

    addHolding({
      ticker: 'wyy',
      shares: 10,
      avg_cost: 5,
      current_price: 6,
      sector: 'Technology',
    });
    addHolding({
      ticker: 'WYY',
      shares: 5,
      avg_cost: 8,
      current_price: 9,
      sector: 'Technology',
    });

    const holdings = useAppStore.getState().portfolio.holdings;
    expect(holdings).toHaveLength(1);
    expect(holdings[0].ticker).toBe('WYY');
    expect(holdings[0].shares).toBe(15);
    expect(holdings[0].avg_cost).toBe(6);
    expect(holdings[0].current_price).toBe(9);
  });
});
