"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { AsOfBadge } from '@/components/AsOfBadge';
import { CopyHoldingAdvisorPrompt } from '@/components/CopyHoldingAdvisorPrompt';
import { ImportTransactions } from '@/components/ImportTransactions';
import { SentimentReport } from '@/components/SentimentReport';
import {
  LevelBlock,
  PortfolioHoldingWithLevels,
  RealizedTrade,
  SentimentSelection,
  deleteTransaction,
  fetchHoldings,
  getPortfolioState,
  putPortfolioState,
  recordTransactions,
} from '@/lib/api';
import { portfolioSyncPayload } from '@/components/PortfolioSync';
import { COPY } from '@/lib/copy';
import { formatMoney } from '@/lib/format';
import { computeImportedHoldings } from '@/lib/importedHoldings';
import { Transaction, effectiveTotalCapital, useAppStore } from '@/lib/store';

/**
 * Transactions page (Feature 019, US2). All buy/sell recording, Google-Sheet
 * import, the chronological transaction ledger, the realized-trades detail, and
 * the per-holding Remove controls live here — relocated (not redesigned) off the
 * Portfolio page. All three write paths (Sheet import, in-app record, delete)
 * converge on the same server-owned `transactions` list via
 * `syncFromServer`/`loadHoldings`, so returning to Portfolio reflects changes
 * immediately (US2 AC3).
 */

type TransactionForm = {
  ticker: string;
  action: 'buy' | 'sell';
  quantity: string;
  price: string;
  trade_date: string;
  fees: string;
};

function blankTransactionForm(): TransactionForm {
  return { ticker: '', action: 'buy', quantity: '', price: '', trade_date: '', fees: '' };
}

function percent(value: number) {
  return `${(value * 100).toFixed(1)}%`;
}

/** Within this fraction of the stop/target, a holding is flagged as "near" its level. */
const NEAR_LEVEL_PCT = 0.03;

interface HoldingAlert {
  ticker: string;
  severity: 'high' | 'medium';
  message: string;
}

function levelStatusLabel(status: LevelBlock['status']) {
  if (status === 'stop_breached') return 'Stop breached';
  if (status === 'target_reached') return 'Target reached';
  if (status === 'gains_protected') return 'Gains protected';
  if (status === 'insufficient_data') return 'Insufficient data';
  return 'Holding';
}

function levelSummary(block?: LevelBlock | null, ticker?: string) {
  if (!block || block.levels_state === 'insufficient_data') {
    return <span className="text-gray-500">Insufficient data</span>;
  }
  return (
    <div className="space-y-1">
      <div>
        <span className="text-gray-500">Stop </span>
        <span>{block.stop_loss ? formatMoney(block.stop_loss, ticker) : '-'}</span>
      </div>
      <div>
        <span className="text-gray-500">Target </span>
        <span>{block.take_profit ? formatMoney(block.take_profit, ticker) : '-'}</span>
      </div>
      <div
        className={
          block.status === 'gains_protected'
            ? 'text-xs font-medium text-emerald-700'
            : 'text-xs text-gray-500'
        }
      >
        {levelStatusLabel(block.status)}
        {block.distance_to_stop_pct !== null && block.distance_to_stop_pct !== undefined
          ? `, stop ${percent(block.distance_to_stop_pct)}`
          : ''}
        {block.distance_to_target_pct !== null && block.distance_to_target_pct !== undefined
          ? `, target ${percent(block.distance_to_target_pct)}`
          : ''}
      </div>
    </div>
  );
}

/** Trailing (chandelier) protective level. Neutral graceful-degradation copy when
 * absent (price at/below cost or the chandelier value is missing — never a
 * fabricated looser level). */
function trailingSummary(block?: LevelBlock | null, ticker?: string) {
  if (!block || block.levels_state === 'insufficient_data') {
    return <span className="text-gray-500">No additional protection</span>;
  }
  return (
    <div className="space-y-1">
      <div>
        <span className="text-gray-500">Stop </span>
        <span>{block.stop_loss ? formatMoney(block.stop_loss, ticker) : '-'}</span>
      </div>
      <div
        className={
          block.status === 'gains_protected'
            ? 'text-xs font-medium text-emerald-700'
            : 'text-xs text-gray-500'
        }
      >
        {levelStatusLabel(block.status)}
        {block.distance_to_stop_pct !== null && block.distance_to_stop_pct !== undefined
          ? `, stop ${percent(block.distance_to_stop_pct)}`
          : ''}
      </div>
    </div>
  );
}

function riskBindingLabel(value?: string | null) {
  if (value === 'per_trade_budget') return 'Per-trade risk budget';
  if (value === 'position_cap') return 'Position cap';
  if (value === 'sector_cap') return 'Sector cap';
  return 'Within configured limits';
}

function riskSummary(detail?: PortfolioHoldingWithLevels, ticker?: string) {
  const risk = detail?.risk;
  if (!risk) {
    return <span className="text-gray-500">Not available</span>;
  }
  return (
    <div className="space-y-1">
      <div>
        <span className="text-gray-500">Suggested </span>
        <span>
          {risk.recommended_shares.toLocaleString()} shares / {formatMoney(risk.recommended_value, ticker)}
        </span>
      </div>
      <div>
        <span className="text-gray-500">Actual </span>
        <span>
          {Number(risk.actual_shares).toLocaleString(undefined, { maximumFractionDigits: 4 })} shares / {formatMoney(risk.actual_value, ticker)}
        </span>
      </div>
      <div className="text-xs text-gray-500">
        Capital at risk {formatMoney(risk.actual_capital_at_risk, ticker)}
        {' '}
        ({percent(risk.actual_capital_at_risk_pct)})
      </div>
      <div className={risk.over_risk ? 'text-xs font-medium text-amber-800' : 'text-xs text-gray-500'}>
        {risk.over_risk ? `Over risk: ${riskBindingLabel(risk.binding_constraint)}` : riskBindingLabel(null)}
      </div>
      {risk.fail_open ? <div className="text-xs text-gray-500">Baseline sizing used</div> : null}
    </div>
  );
}

export default function TransactionsPage() {
  const portfolio = useAppStore((state) => state.portfolio);
  const settings = useAppStore((state) => state.settings);
  const setTransactions = useAppStore((s) => s.setTransactions);
  const removeTransactionsForTicker = useAppStore((s) => s.removeTransactionsForTicker);
  const storeTransactions = useAppStore((s) => s.transactions);

  const importedHoldings = useMemo(
    () => computeImportedHoldings(storeTransactions),
    [storeTransactions],
  );

  const [importedDetails, setImportedDetails] = useState<Record<string, PortfolioHoldingWithLevels>>({});
  const [importedAsOf, setImportedAsOf] = useState<string | null>(null);
  const [importedTotals, setImportedTotals] = useState<{
    total_invested: string;
    total_capital_at_risk: string;
    total_capital_at_risk_pct: number;
    heat_ceiling_pct?: number;
    heat_headroom_pct?: number;
    realized_pnl?: string | null;
    unrealized_pnl?: string | null;
    total_pnl?: string | null;
    win_rate?: number | null;
    closed_trade_count?: number;
    winning_trade_count?: number;
  } | null>(null);
  const [realizedTrades, setRealizedTrades] = useState<RealizedTrade[]>([]);
  const [importedDetailsLoading, setImportedDetailsLoading] = useState(false);
  const [importedDetailsError, setImportedDetailsError] = useState<string | null>(null);
  const [removingTicker, setRemovingTicker] = useState<string | null>(null);
  const [txnForm, setTxnForm] = useState<TransactionForm>(blankTransactionForm());
  const [txnBusy, setTxnBusy] = useState(false);
  const [txnError, setTxnError] = useState<string | null>(null);
  const [txnRejected, setTxnRejected] = useState<string[]>([]);
  const [removingTxnId, setRemovingTxnId] = useState<string | null>(null);
  const [sentimentTickers, setSentimentTickers] = useState<Set<string>>(() => new Set());
  const [sentimentSelections, setSentimentSelections] = useState<SentimentSelection[] | null>(null);

  function toggleSentimentTicker(ticker: string) {
    setSentimentTickers((current) => {
      const next = new Set(current);
      if (next.has(ticker)) {
        next.delete(ticker);
      } else {
        next.add(ticker);
      }
      return next;
    });
  }

  function runHoldingsSentiment() {
    if (!sentimentTickers.size) return;
    setSentimentSelections(
      Array.from(sentimentTickers).map((ticker) => ({ ticker, origin: 'holding' as const })),
    );
  }

  // Re-fetch the server blob and sync the retained transactions into the store.
  // Shared by Sheet import and in-app record/delete so all three converge on the
  // same server-owned transactions list.
  const syncFromServer = useCallback(async () => {
    try {
      const resp = await getPortfolioState();
      if (resp.state) {
        const raw = resp.state as Record<string, unknown>;
        const txns = Array.isArray(raw.transactions) ? (raw.transactions as Transaction[]) : [];
        const sheetId = typeof raw.sheet_id === 'string' ? raw.sheet_id : null;
        const sheetRange = typeof raw.sheet_range === 'string' ? raw.sheet_range : null;
        setTransactions(txns, sheetId, sheetRange);
      }
    } catch {
      // Backend unreachable — the store keeps its current data.
    }
  }, [setTransactions]);

  // Fetch the purchase-anchored levels / sizing for the imported holdings.
  const loadHoldings = useCallback(async () => {
    if (!useAppStore.getState().transactions.length) {
      setImportedDetails({});
      setImportedAsOf(null);
      setImportedTotals(null);
      setRealizedTrades([]);
      return;
    }
    setImportedDetailsLoading(true);
    setImportedDetailsError(null);
    try {
      const activePortfolio = useAppStore.getState().portfolio;
      const capital = effectiveTotalCapital(activePortfolio);
      const response = await fetchHoldings({
        total_capital: String(capital || 1),
        strategy_slug: settings.default_strategy_slug,
        available_cash:
          activePortfolio.available_cash != null
            ? String(activePortfolio.available_cash)
            : undefined,
      });
      setImportedDetails(Object.fromEntries(response.holdings.map((holding) => [holding.ticker, holding])));
      setImportedAsOf(response.data_as_of);
      setImportedTotals(response.totals);
      setRealizedTrades(response.realized_trades ?? []);
    } catch {
      setImportedDetailsError('Imported holding levels are unavailable.');
    } finally {
      setImportedDetailsLoading(false);
    }
  }, [settings.default_strategy_slug]);

  useEffect(() => {
    // Defer out of the synchronous effect body (loadHoldings may setState
    // immediately when the ledger is empty) to avoid cascading renders.
    const id = window.setTimeout(() => {
      loadHoldings();
    }, 0);
    return () => window.clearTimeout(id);
  }, [loadHoldings, storeTransactions]);

  // After a successful import, re-fetch the server blob to sync transactions into the store.
  const handleImported = useCallback(async () => {
    await syncFromServer();
  }, [syncFromServer]);

  // Remove one ticker's imported transactions (and its derived holding).
  const handleRemoveImportedHolding = useCallback(
    async (ticker: string) => {
      if (typeof window !== 'undefined') {
        const confirmed = window.confirm(
          `Remove ${ticker} from your imported holdings? This deletes its imported transactions from this portfolio. Re-import from your sheet to restore them.`,
        );
        if (!confirmed) return;
      }
      setRemovingTicker(ticker);
      removeTransactionsForTicker(ticker);
      try {
        await putPortfolioState(portfolioSyncPayload(useAppStore.getState()));
      } catch {
        // Local store is already updated; PortfolioSync will retry the push.
      }
      try {
        await loadHoldings();
      } finally {
        setRemovingTicker(null);
      }
    },
    [removeTransactionsForTicker, loadHoldings],
  );

  // Record one manual transaction. Reuses the same server validator + retained
  // list as the Sheet import (parity, SC-010), then re-syncs and re-aggregates.
  const handleRecordTransaction = useCallback(
    async (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      setTxnError(null);
      setTxnRejected([]);
      setTxnBusy(true);
      try {
        const row: Record<string, unknown> = {
          ticker: txnForm.ticker.trim().toUpperCase(),
          action: txnForm.action,
          quantity: txnForm.quantity,
          price: txnForm.price,
          trade_date: txnForm.trade_date,
          source_row: Math.floor(Date.now() / 1000),
        };
        if (txnForm.fees.trim()) row.fees = txnForm.fees;
        const result = await recordTransactions([row]);
        if (result.rejected.length > 0) {
          setTxnRejected(result.rejected.map((r) => r.reason));
        } else {
          setTxnForm(blankTransactionForm());
        }
        await syncFromServer();
        await loadHoldings();
      } catch {
        setTxnError('Could not record the transaction. Please try again.');
      } finally {
        setTxnBusy(false);
      }
    },
    [txnForm, syncFromServer, loadHoldings],
  );

  // Delete one retained transaction by id (correct a mistake), then re-aggregate.
  const handleDeleteTransaction = useCallback(
    async (id: string) => {
      if (typeof window !== 'undefined') {
        const confirmed = window.confirm('Delete this transaction? Holdings and P&L will be recomputed.');
        if (!confirmed) return;
      }
      setRemovingTxnId(id);
      try {
        await deleteTransaction(id);
        await syncFromServer();
        await loadHoldings();
      } catch {
        setTxnError('Could not delete the transaction. Please try again.');
      } finally {
        setRemovingTxnId(null);
      }
    },
    [syncFromServer, loadHoldings],
  );

  // Surface holdings that have reached/passed — or are near — their current-condition
  // stop or target. Descriptive only (no directive language, FR-020).
  const holdingAlerts = useMemo<HoldingAlert[]>(() => {
    const alerts: HoldingAlert[] = [];
    for (const h of importedHoldings) {
      if (h.status !== 'open') continue;
      const detail = importedDetails[h.ticker];
      const block = detail?.levels?.current_condition;
      if (!detail?.priceable || !block || block.levels_state !== 'ok') continue;
      const priceLabel = detail.current_price ? formatMoney(detail.current_price, h.ticker) : null;
      const suffix = priceLabel ? ` (now ${priceLabel})` : '';
      if (block.status === 'stop_breached') {
        alerts.push({ ticker: h.ticker, severity: 'high', message: `${h.ticker} has passed its stop level${suffix}.` });
        continue;
      }
      if (block.status === 'target_reached') {
        alerts.push({ ticker: h.ticker, severity: 'high', message: `${h.ticker} has reached its target level${suffix}.` });
        continue;
      }
      const stopDist = block.distance_to_stop_pct;
      const targetDist = block.distance_to_target_pct;
      if (stopDist !== null && stopDist !== undefined && Math.abs(stopDist) <= NEAR_LEVEL_PCT) {
        alerts.push({
          ticker: h.ticker,
          severity: 'medium',
          message: `${h.ticker} is near its stop level (${percent(Math.abs(stopDist))} away).`,
        });
      } else if (targetDist !== null && targetDist !== undefined && targetDist > 0 && targetDist <= NEAR_LEVEL_PCT) {
        alerts.push({
          ticker: h.ticker,
          severity: 'medium',
          message: `${h.ticker} is near its target level (${percent(targetDist)} away).`,
        });
      }
    }
    return alerts;
  }, [importedHoldings, importedDetails]);

  const cashSet = portfolio.available_cash != null;
  const importedMarketValue = importedTotals ? Number(importedTotals.total_invested) : 0;
  const derivedTotalCapital = cashSet
    ? effectiveTotalCapital(portfolio) + importedMarketValue
    : portfolio.total_capital;

  return (
    <main className="mx-auto max-w-6xl space-y-6 px-6 py-8">
      <header className="border-b border-gray-200 pb-5">
        <h1 className="text-2xl font-semibold text-gray-950">Transactions</h1>
        <div className="mt-2 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-sm text-gray-600">
            Buy/sell ledger, Google Sheet import, and per-holding controls. Changes here reflect on
            your{' '}
            <Link className="font-semibold text-gray-950 underline" href="/portfolio">
              Portfolio
            </Link>{' '}
            immediately.
          </p>
          {importedAsOf ? <AsOfBadge date={importedAsOf} /> : null}
        </div>
      </header>
      {importedDetailsError ? (
        <div className="border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">{importedDetailsError}</div>
      ) : null}

      {/* ------------------------------------------------------------------ */}
      {/* Feature 013 — Import transactions from Google Sheet                  */}
      {/* ------------------------------------------------------------------ */}
      <ImportTransactions onImported={handleImported} />

      {/* ------------------------------------------------------------------ */}
      {/* Feature 016 (US4) — Record a buy/sell in-app (secondary to import)   */}
      {/* ------------------------------------------------------------------ */}
      <section
        aria-label="Record a transaction"
        className="space-y-3 border border-gray-200 p-5"
        data-transaction-record
      >
        <div>
          <h2 className="text-lg font-semibold text-gray-950">Record a Transaction</h2>
          <p className="text-xs text-gray-500">
            Enter a single buy or sell. Google Sheet import remains available above for bulk entry.
          </p>
        </div>
        <form className="grid gap-3 sm:grid-cols-6" onSubmit={handleRecordTransaction}>
          <label className="block text-sm text-gray-800 sm:col-span-1">
            <span className="font-medium">Ticker</span>
            <input
              aria-label="Transaction ticker"
              className="mt-1 w-full border border-gray-300 px-3 py-2 uppercase"
              onChange={(e) => setTxnForm((f) => ({ ...f, ticker: e.target.value }))}
              required
              value={txnForm.ticker}
            />
          </label>
          <label className="block text-sm text-gray-800 sm:col-span-1">
            <span className="font-medium">Action</span>
            <select
              aria-label="Transaction action"
              className="mt-1 w-full border border-gray-300 px-3 py-2"
              onChange={(e) => setTxnForm((f) => ({ ...f, action: e.target.value as 'buy' | 'sell' }))}
              value={txnForm.action}
            >
              <option value="buy">Buy</option>
              <option value="sell">Sell</option>
            </select>
          </label>
          <label className="block text-sm text-gray-800 sm:col-span-1">
            <span className="font-medium">Quantity</span>
            <input
              aria-label="Transaction quantity"
              className="mt-1 w-full border border-gray-300 px-3 py-2"
              min={0}
              onChange={(e) => setTxnForm((f) => ({ ...f, quantity: e.target.value }))}
              required
              step={0.0001}
              type="number"
              value={txnForm.quantity}
            />
          </label>
          <label className="block text-sm text-gray-800 sm:col-span-1">
            <span className="font-medium">Price</span>
            <input
              aria-label="Transaction price"
              className="mt-1 w-full border border-gray-300 px-3 py-2"
              min={0}
              onChange={(e) => setTxnForm((f) => ({ ...f, price: e.target.value }))}
              required
              step={0.01}
              type="number"
              value={txnForm.price}
            />
          </label>
          <label className="block text-sm text-gray-800 sm:col-span-1">
            <span className="font-medium">Trade date</span>
            <input
              aria-label="Transaction date"
              className="mt-1 w-full border border-gray-300 px-3 py-2"
              onChange={(e) => setTxnForm((f) => ({ ...f, trade_date: e.target.value }))}
              required
              type="date"
              value={txnForm.trade_date}
            />
          </label>
          <label className="block text-sm text-gray-800 sm:col-span-1">
            <span className="font-medium">Fees</span>
            <input
              aria-label="Transaction fees"
              className="mt-1 w-full border border-gray-300 px-3 py-2"
              min={0}
              onChange={(e) => setTxnForm((f) => ({ ...f, fees: e.target.value }))}
              placeholder="Optional"
              step={0.01}
              type="number"
              value={txnForm.fees}
            />
          </label>
          <div className="sm:col-span-6">
            <button
              className="border border-gray-950 bg-gray-950 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
              disabled={txnBusy}
              type="submit"
            >
              {txnBusy ? 'Recording…' : 'Record transaction'}
            </button>
          </div>
        </form>
        {txnError ? (
          <div className="border border-amber-300 bg-amber-50 p-2 text-sm text-amber-900">{txnError}</div>
        ) : null}
        {txnRejected.length > 0 ? (
          <div className="border border-amber-300 bg-amber-50 p-2 text-sm text-amber-900">
            Row rejected: {txnRejected.join('; ')}
          </div>
        ) : null}
        {storeTransactions.length > 0 ? (
          <div className="overflow-x-auto border border-gray-200">
            <table className="min-w-full text-left text-sm">
              <thead className="bg-gray-50 text-xs uppercase text-gray-500">
                <tr>
                  <th className="px-3 py-2">Date</th>
                  <th className="px-3 py-2">Ticker</th>
                  <th className="px-3 py-2">Action</th>
                  <th className="px-3 py-2 text-right">Quantity</th>
                  <th className="px-3 py-2 text-right">Price</th>
                  <th className="px-3 py-2 text-right">Fees</th>
                  <th className="px-3 py-2 text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {[...storeTransactions]
                  .sort(
                    (a, b) =>
                      a.trade_date.localeCompare(b.trade_date) || a.source_row - b.source_row,
                  )
                  .map((t) => (
                    <tr className="border-t border-gray-200" key={t.id}>
                      <td className="px-3 py-2 text-gray-700">{t.trade_date}</td>
                      <td className="px-3 py-2 font-semibold text-gray-950">{t.ticker}</td>
                      <td className="px-3 py-2 text-gray-700">{t.action === 'buy' ? 'Buy' : 'Sell'}</td>
                      <td className="px-3 py-2 text-right text-gray-700">
                        {Number(t.quantity).toLocaleString(undefined, { maximumFractionDigits: 4 })}
                      </td>
                      <td className="px-3 py-2 text-right text-gray-700">{formatMoney(t.price, t.ticker)}</td>
                      <td className="px-3 py-2 text-right text-gray-700">
                        {t.fees ? formatMoney(t.fees, t.ticker) : '-'}
                      </td>
                      <td className="px-3 py-2 text-right">
                        <button
                          className="border border-gray-300 px-3 py-1 text-xs font-medium text-gray-800 hover:bg-gray-50 disabled:opacity-50"
                          disabled={removingTxnId === t.id}
                          onClick={() => handleDeleteTransaction(t.id)}
                          type="button"
                        >
                          {removingTxnId === t.id ? 'Deleting…' : 'Delete'}
                        </button>
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </section>

      {importedHoldings.length > 0 ? (
        <section aria-label="Imported holdings ledger" className="space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-lg font-semibold text-gray-950">Imported Holdings</h2>
            <div className="flex flex-wrap items-center gap-2">
              <button
                className="border border-gray-300 px-3 py-2 text-sm font-semibold text-gray-800 disabled:opacity-50"
                disabled={sentimentTickers.size === 0}
                onClick={runHoldingsSentiment}
                type="button"
              >
                Run sentiment report{sentimentTickers.size ? ` (${sentimentTickers.size})` : ''}
              </button>
              <CopyHoldingAdvisorPrompt
                totalCapital={String(derivedTotalCapital || 1)}
                strategySlug={settings.default_strategy_slug}
              />
            </div>
          </div>
          <p className="text-xs text-gray-500">
            Derived from {storeTransactions.length} imported transaction{storeTransactions.length !== 1 ? 's' : ''}.
            {importedDetailsLoading ? ' Level details are refreshing.' : ' Level details are recomputed from the latest snapshot.'}
          </p>
          {holdingAlerts.length > 0 ? (
            <div aria-label="Holding level alerts" className="space-y-2">
              {holdingAlerts.map((alert) => (
                <div
                  className={
                    alert.severity === 'high'
                      ? 'border border-rose-300 bg-rose-50 px-3 py-2 text-sm font-medium text-rose-900'
                      : 'border border-amber-300 bg-amber-50 px-3 py-2 text-sm font-medium text-amber-900'
                  }
                  key={`${alert.ticker}-${alert.message}`}
                  role="alert"
                >
                  {alert.message}
                </div>
              ))}
            </div>
          ) : null}
          {importedTotals ? (
            <div className="grid gap-3 sm:grid-cols-4">
              <div className="border border-gray-200 p-3">
                <div className="text-xs uppercase text-gray-500">Total invested</div>
                <div className="text-lg font-semibold text-gray-950">{formatMoney(importedTotals.total_invested)}</div>
              </div>
              <div className="border border-gray-200 p-3">
                <div className="text-xs uppercase text-gray-500">Total capital at risk</div>
                <div className="text-lg font-semibold text-gray-950">{formatMoney(importedTotals.total_capital_at_risk)}</div>
              </div>
              <div className="border border-gray-200 p-3">
                <div className="text-xs uppercase text-gray-500">Risk as % of capital</div>
                <div className="text-lg font-semibold text-gray-950">{percent(importedTotals.total_capital_at_risk_pct)}</div>
              </div>
              <div className="border border-gray-200 p-3">
                <div className="text-xs uppercase text-gray-500">Portfolio-heat headroom</div>
                <div className="text-lg font-semibold text-gray-950">
                  {importedTotals.heat_headroom_pct !== undefined
                    ? percent(importedTotals.heat_headroom_pct)
                    : '-'}
                </div>
                {importedTotals.heat_ceiling_pct !== undefined && importedTotals.heat_ceiling_pct > 0 ? (
                  <div className="mt-1 text-xs text-gray-500">
                    ceiling {percent(importedTotals.heat_ceiling_pct)}
                  </div>
                ) : null}
              </div>
            </div>
          ) : null}
          {realizedTrades.length > 0 ? (
            <details className="border border-gray-200" data-transaction-record>
              <summary className="cursor-pointer px-4 py-3 text-sm font-semibold text-gray-800">
                Realized trades ({realizedTrades.length})
              </summary>
              <div className="overflow-x-auto border-t border-gray-200">
                <table className="min-w-full text-left text-sm">
                  <thead className="bg-gray-50 text-xs uppercase text-gray-500">
                    <tr>
                      <th className="px-4 py-3">Ticker</th>
                      <th className="px-4 py-3 text-right">Shares</th>
                      <th className="px-4 py-3">Buy date</th>
                      <th className="px-4 py-3">Sell date</th>
                      <th className="px-4 py-3 text-right">Proceeds</th>
                      <th className="px-4 py-3 text-right">Cost basis</th>
                      <th className="px-4 py-3 text-right">Fees</th>
                      <th className="px-4 py-3 text-right">Realized P/L</th>
                      <th className="px-4 py-3">Outcome</th>
                      <th className="px-4 py-3 text-right">Held (days)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {realizedTrades.map((t, i) => (
                      <tr className="border-t border-gray-200" key={`${t.ticker}-${t.buy_date}-${t.sell_date}-${i}`}>
                        <td className="px-4 py-3 font-semibold text-gray-950">{t.ticker}</td>
                        <td className="px-4 py-3 text-right text-gray-700">
                          {Number(t.shares).toLocaleString(undefined, { maximumFractionDigits: 4 })}
                        </td>
                        <td className="px-4 py-3 text-gray-700">{t.buy_date}</td>
                        <td className="px-4 py-3 text-gray-700">{t.sell_date}</td>
                        <td className="px-4 py-3 text-right text-gray-700">{formatMoney(t.proceeds, t.ticker)}</td>
                        <td className="px-4 py-3 text-right text-gray-700">{formatMoney(t.cost_basis, t.ticker)}</td>
                        <td className="px-4 py-3 text-right text-gray-700">{formatMoney(t.fees, t.ticker)}</td>
                        <td
                          className={
                            Number(t.realized_pnl) < 0
                              ? 'px-4 py-3 text-right text-rose-700'
                              : 'px-4 py-3 text-right text-emerald-700'
                          }
                        >
                          {formatMoney(t.realized_pnl, t.ticker)}
                        </td>
                        <td className="px-4 py-3 text-gray-700 capitalize">{t.outcome}</td>
                        <td className="px-4 py-3 text-right text-gray-700">{t.holding_days}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </details>
          ) : null}
          <div className="overflow-x-auto border border-gray-200">
            <table className="min-w-full text-left text-sm">
              <thead className="bg-gray-50 text-xs uppercase text-gray-500">
                <tr>
                  <th className="px-4 py-3">Report</th>
                  <th className="px-4 py-3">Ticker</th>
                  <th className="px-4 py-3 text-right">Net shares</th>
                  <th className="px-4 py-3 text-right">Avg cost</th>
                  <th className="px-4 py-3">First purchase</th>
                  <th className="px-4 py-3">Latest purchase</th>
                  <th className="px-4 py-3 text-right">Current price</th>
                  <th className="px-4 py-3 text-right">Unrealized P/L</th>
                  <th className="px-4 py-3">Original plan</th>
                  <th className="px-4 py-3">Current condition</th>
                  <th className="px-4 py-3">Trailing</th>
                  <th className="px-4 py-3">Sizing & risk</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {importedHoldings.map((h) => {
                  const detail = importedDetails[h.ticker];
                  return (
                    <tr className="border-t border-gray-200" key={h.ticker}>
                      <td className="px-4 py-3">
                        <input
                          aria-label={`Select ${h.ticker} for sentiment report`}
                          checked={sentimentTickers.has(h.ticker)}
                          onChange={() => toggleSentimentTicker(h.ticker)}
                          type="checkbox"
                        />
                      </td>
                      <td className="px-4 py-3 font-semibold text-gray-950">{h.ticker}</td>
                      <td className="px-4 py-3 text-right text-gray-700">
                        {h.net_quantity.toLocaleString(undefined, { maximumFractionDigits: 4 })}
                      </td>
                      <td className="px-4 py-3 text-right text-gray-700">
                        {formatMoney(h.avg_cost, h.ticker)}
                      </td>
                      <td className="px-4 py-3 text-gray-700">{h.earliest_buy_date}</td>
                      <td className="px-4 py-3 text-gray-700">{h.most_recent_buy_date}</td>
                      <td className="px-4 py-3 text-right text-gray-700">
                        {detail?.current_price ? formatMoney(detail.current_price, h.ticker) : '-'}
                      </td>
                      <td className="px-4 py-3 text-right">
                        {detail?.unrealized_pl ? (
                          <span className={Number(detail.unrealized_pl) >= 0 ? 'text-emerald-700' : 'text-rose-700'}>
                            {formatMoney(detail.unrealized_pl, h.ticker)}
                            {detail.unrealized_pl_pct !== null && detail.unrealized_pl_pct !== undefined
                              ? ` (${percent(detail.unrealized_pl_pct)})`
                              : ''}
                          </span>
                        ) : (
                          <span className="text-gray-500">-</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-gray-700">{levelSummary(detail?.levels?.original_plan, h.ticker)}</td>
                      <td className="px-4 py-3 text-gray-700">{levelSummary(detail?.levels?.current_condition, h.ticker)}</td>
                      <td className="px-4 py-3 text-gray-700">{trailingSummary(detail?.levels?.trailing, h.ticker)}</td>
                      <td className="px-4 py-3 text-gray-700">{riskSummary(detail, h.ticker)}</td>
                      <td className="px-4 py-3">
                        {detail && !detail.priceable ? (
                          <span className="text-amber-800">{detail.data_notes[0] ?? 'Out of coverage'}</span>
                        ) : h.status === 'open' ? (
                          <span className="text-gray-700">Open</span>
                        ) : h.status === 'closed' ? (
                          <span className="text-gray-500">Closed</span>
                        ) : (
                          <span className="text-amber-800">Anomalous - net quantity is negative</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <div className="flex flex-col items-end gap-2">
                          {h.status === 'open' && detail?.priceable ? (
                            <CopyHoldingAdvisorPrompt
                              totalCapital={String(derivedTotalCapital || 1)}
                              ticker={h.ticker}
                              strategySlug={settings.default_strategy_slug}
                            />
                          ) : null}
                          <button
                            className="border border-gray-300 px-3 py-1 text-xs font-medium text-gray-800 hover:bg-gray-50 disabled:opacity-50"
                            disabled={removingTicker === h.ticker}
                            onClick={() => handleRemoveImportedHolding(h.ticker)}
                            type="button"
                          >
                            {removingTicker === h.ticker ? 'Removing…' : 'Remove'}
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      ) : (
        <section className="border border-gray-200 p-6 text-sm text-gray-600">
          No transactions yet. Record a buy/sell above or import from your Google Sheet, and your
          positions will appear on the{' '}
          <Link className="font-semibold text-gray-950 underline" href="/portfolio">
            Portfolio
          </Link>{' '}
          page.
        </section>
      )}

      {sentimentSelections ? (
        <section aria-label="Holdings sentiment report" className="space-y-3">
          <h2 className="text-lg font-semibold text-gray-950">Holdings Sentiment Report</h2>
          <SentimentReport
            initialSelections={sentimentSelections}
            key={sentimentSelections.map((selection) => selection.ticker).join(',')}
          />
        </section>
      ) : null}

      <p className="text-xs text-gray-500">{COPY.GLOBAL.DISCLAIMER}</p>
    </main>
  );
}
