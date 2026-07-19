import { describe, expect, it } from 'vitest';

import { computeImportedHoldings } from '@/lib/importedHoldings';
import type { Transaction } from '@/lib/store';

/**
 * Feature 019 US3 (T019): closed positions leave the Portfolio page.
 *
 * The Portfolio card list is derived by `openPositionCards`, which maps only the
 * holdings whose `status === 'open'` (i.e. `net_quantity > 0`) onto fetched
 * card details. These tests pin that filter at the derivation seam
 * (`computeImportedHoldings` + the `status === 'open'` predicate the page applies)
 * so a zero-net (fully sold) holding produces no card and a later repurchase
 * reintroduces one (FR-003 / FR-011, SC-002).
 */

let seq = 0;
function txn(over: Partial<Transaction>): Transaction {
  seq += 1;
  return {
    id: `t${seq}`,
    ticker: 'NVDA',
    action: 'buy',
    quantity: '100',
    price: '100',
    trade_date: '2026-01-01',
    fees: null,
    note: null,
    source_row: seq,
    ...over,
  };
}

/** Tickers the Portfolio page would render as open-position cards. */
function openCardTickers(transactions: Transaction[]): string[] {
  return computeImportedHoldings(transactions)
    .filter((h) => h.status === 'open')
    .map((h) => h.ticker);
}

describe('Portfolio open-position card filter (US3)', () => {
  it('includes only holdings with net_quantity > 0', () => {
    const transactions: Transaction[] = [
      // AAPL: bought and never sold → open.
      txn({ ticker: 'AAPL', action: 'buy', quantity: '50', trade_date: '2026-01-02', source_row: 1 }),
      // MSFT: bought then fully sold → net 0 → closed, no card.
      txn({ ticker: 'MSFT', action: 'buy', quantity: '30', trade_date: '2026-01-03', source_row: 2 }),
      txn({ ticker: 'MSFT', action: 'sell', quantity: '30', trade_date: '2026-02-01', source_row: 3 }),
      // NVDA: bought 100, sold 40 → net 60 → open.
      txn({ ticker: 'NVDA', action: 'buy', quantity: '100', trade_date: '2026-01-04', source_row: 4 }),
      txn({ ticker: 'NVDA', action: 'sell', quantity: '40', trade_date: '2026-02-02', source_row: 5 }),
    ];

    expect(openCardTickers(transactions)).toEqual(['AAPL', 'NVDA']);
  });

  it('drops a card once the position is fully sold', () => {
    const transactions: Transaction[] = [
      txn({ ticker: 'TSLA', action: 'buy', quantity: '20', trade_date: '2026-01-05', source_row: 1 }),
      txn({ ticker: 'TSLA', action: 'sell', quantity: '20', trade_date: '2026-03-01', source_row: 2 }),
    ];

    expect(openCardTickers(transactions)).not.toContain('TSLA');
    expect(openCardTickers(transactions)).toEqual([]);
  });

  it('reintroduces a card when the position is repurchased (net back above 0)', () => {
    const base: Transaction[] = [
      txn({ ticker: 'AMD', action: 'buy', quantity: '10', trade_date: '2026-01-06', source_row: 1 }),
      txn({ ticker: 'AMD', action: 'sell', quantity: '10', trade_date: '2026-02-06', source_row: 2 }),
    ];
    expect(openCardTickers(base)).toEqual([]);

    const repurchased: Transaction[] = [
      ...base,
      txn({ ticker: 'AMD', action: 'buy', quantity: '15', trade_date: '2026-03-06', source_row: 3 }),
    ];
    expect(openCardTickers(repurchased)).toEqual(['AMD']);
  });
});
