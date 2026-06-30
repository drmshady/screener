import { beforeEach, describe, expect, test } from 'vitest';
import { portfolioSyncPayload } from '../../src/components/PortfolioSync';
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
      transactions: [],
      sheet_id: null,
      sheet_range: null,
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

  test('portfolio sync payload preserves imported transactions and sheet metadata', () => {
    useAppStore.setState({
      transactions: [
        {
          id: 'abc#0',
          ticker: 'MSFT',
          action: 'buy',
          quantity: '5',
          price: '400.00',
          trade_date: '2025-08-15',
          fees: '1.00',
          note: null,
          source_row: 3,
        },
      ],
      sheet_id: 'sheet123',
      sheet_range: 'Transactions!A1:I',
    });

    const payload = portfolioSyncPayload(useAppStore.getState());

    expect(payload.transactions).toHaveLength(1);
    expect(payload.transactions[0].id).toBe('abc#0');
    expect(payload.sheet_id).toBe('sheet123');
    expect(payload.sheet_range).toBe('Transactions!A1:I');
  });
});
