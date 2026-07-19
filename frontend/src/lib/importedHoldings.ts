import type { Transaction } from '@/lib/store';

/** Per-ticker summary derived from imported transactions (frontend MVP aggregation). */
export interface ImportedHolding {
  ticker: string;
  net_quantity: number;
  avg_cost: number;
  earliest_buy_date: string;
  most_recent_buy_date: string;
  status: 'open' | 'closed' | 'anomalous';
}

/**
 * Aggregate the retained buy/sell transactions into one average-cost holding per
 * ticker (net quantity, average cost, first/latest buy). Shared by the Portfolio
 * page (open-position cards) and the Transactions page (ledger) so both read the
 * same net-quantity classification from the single server-owned transaction list.
 */
export function computeImportedHoldings(transactions: Transaction[]): ImportedHolding[] {
  const byTicker: Record<string, Transaction[]> = {};
  for (const t of transactions) {
    (byTicker[t.ticker] = byTicker[t.ticker] ?? []).push(t);
  }
  const results: ImportedHolding[] = [];
  for (const [ticker, txns] of Object.entries(byTicker)) {
    const sorted = [...txns].sort(
      (a, b) =>
        a.trade_date.localeCompare(b.trade_date) || a.source_row - b.source_row,
    );
    let totalBuyQty = 0;
    let totalBuyCost = 0;
    let totalSellQty = 0;
    const buyDates: string[] = [];
    for (const t of sorted) {
      const qty = Number(t.quantity);
      const price = Number(t.price);
      if (t.action === 'buy') {
        totalBuyQty += qty;
        totalBuyCost += qty * price;
        buyDates.push(t.trade_date);
      } else {
        totalSellQty += qty;
      }
    }
    const netQty = totalBuyQty - totalSellQty;
    const avgCost = totalBuyQty > 0 ? totalBuyCost / totalBuyQty : 0;
    results.push({
      ticker,
      net_quantity: netQty,
      avg_cost: avgCost,
      earliest_buy_date: buyDates.length > 0 ? buyDates.reduce((a, b) => (a < b ? a : b)) : '',
      most_recent_buy_date: buyDates.length > 0 ? buyDates.reduce((a, b) => (a > b ? a : b)) : '',
      status: netQty > 0 ? 'open' : netQty === 0 ? 'closed' : 'anomalous',
    });
  }
  return results.sort((a, b) => a.ticker.localeCompare(b.ticker));
}
