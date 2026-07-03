"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from 'react';
import { AsOfBadge } from '@/components/AsOfBadge';
import { CopyHoldingAdvisorPrompt } from '@/components/CopyHoldingAdvisorPrompt';
import { ImportTransactions } from '@/components/ImportTransactions';
import { PortfolioAllocationChart } from '@/components/ChartPanels';
import { SentimentReport } from '@/components/SentimentReport';
import { ShariahBadge } from '@/components/ShariahBadge';
import {
  ImportResult,
  LevelBlock,
  PortfolioQuote,
  PortfolioHoldingWithLevels,
  PortfolioQuotesResponseSchema,
  RealizedTrade,
  SentimentSelection,
  ShariahStatus,
  ShariahStatusSchema,
  deleteTransaction,
  fetchApi,
  fetchHoldings,
  getPortfolioState,
  putPortfolioState,
  recordTransactions,
} from '@/lib/api';
import { portfolioSyncPayload } from '@/components/PortfolioSync';
import { COPY } from '@/lib/copy';
import { formatMoney } from '@/lib/format';
import { Holding, Transaction, effectiveTotalCapital, useAppStore } from '@/lib/store';

/** Per-ticker summary derived from imported transactions (frontend MVP aggregation). */
interface ImportedHolding {
  ticker: string;
  net_quantity: number;
  avg_cost: number;
  earliest_buy_date: string;
  most_recent_buy_date: string;
  status: 'open' | 'closed' | 'anomalous';
}

function computeImportedHoldings(transactions: Transaction[]): ImportedHolding[] {
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

const SECTORS = [
  'Communication Services',
  'Consumer Discretionary',
  'Consumer Staples',
  'Energy',
  'Financials',
  'Health Care',
  'Industrials',
  'Information Technology',
  'Materials',
  'Real Estate',
  'Utilities',
  'Unclassified',
];

type HoldingForm = {
  ticker: string;
  shares: string;
  avg_cost: string;
  current_price: string;
  sector: string;
  avg_dollar_volume_20d: string;
  note: string;
};

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

function blankForm(): HoldingForm {
  return {
    ticker: '',
    shares: '',
    avg_cost: '',
    current_price: '',
    sector: 'Unclassified',
    avg_dollar_volume_20d: '',
    note: '',
  };
}

function formFromHolding(holding: Holding): HoldingForm {
  return {
    ticker: holding.ticker,
    shares: String(holding.shares),
    avg_cost: String(holding.avg_cost),
    current_price: String(holding.current_price),
    sector: holding.sector,
    avg_dollar_volume_20d: holding.avg_dollar_volume_20d ? String(holding.avg_dollar_volume_20d) : '',
    note: holding.note ?? '',
  };
}

function money(value: number) {
  return `$${value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
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

function queryFromSettings(settings: ReturnType<typeof useAppStore.getState>['settings']) {
  const params = new URLSearchParams();
  if (settings.shariah_external_sources.length) {
    params.set('sources', settings.shariah_external_sources.join(','));
  }
  if (settings.shariah_user_inclusion.length) {
    params.set('include', settings.shariah_user_inclusion.map((entry) => entry.ticker).join(','));
  }
  if (settings.shariah_user_exclusion.length) {
    params.set('exclude', settings.shariah_user_exclusion.map((entry) => entry.ticker).join(','));
  }
  const query = params.toString();
  return query ? `?${query}` : '';
}

export default function PortfolioPage() {
  const portfolio = useAppStore((state) => state.portfolio);
  const settings = useAppStore((state) => state.settings);
  const setTotalCapital = useAppStore((state) => state.setTotalCapital);
  const setAvailableCash = useAppStore((state) => state.setAvailableCash);
  const addHolding = useAppStore((state) => state.addHolding);
  const updateHolding = useAppStore((state) => state.updateHolding);
  const removeHolding = useAppStore((state) => state.removeHolding);
  const acknowledgeLocalStorageWarning = useAppStore((state) => state.acknowledgeLocalStorageWarning);
  const setTransactions = useAppStore((s) => s.setTransactions);
  const removeTransactionsForTicker = useAppStore((s) => s.removeTransactionsForTicker);
  const storeTransactions = useAppStore((s) => s.transactions);
  const storeSheetId = useAppStore((s) => s.sheet_id);
  const storeSheetRange = useAppStore((s) => s.sheet_range);

  const importedHoldings = useMemo(
    () => computeImportedHoldings(storeTransactions),
    [storeTransactions],
  );

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

  // After a successful import, re-fetch the server blob to sync transactions into the store.
  const handleImported = useCallback(
    async (_result: ImportResult) => {
      await syncFromServer();
    },
    [syncFromServer],
  );

  const [statuses, setStatuses] = useState<Record<string, ShariahStatus>>({});
  const [form, setForm] = useState<HoldingForm>(blankForm());
  const [editingTicker, setEditingTicker] = useState<string | null>(null);
  const [showStorageWarning, setShowStorageWarning] = useState(false);
  const [quotes, setQuotes] = useState<Record<string, PortfolioQuote>>({});
  const [quotesAsOf, setQuotesAsOf] = useState<string | null>(null);
  const [quotesLoading, setQuotesLoading] = useState(false);
  const [quotesError, setQuotesError] = useState<string | null>(null);
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
  // US4 (feature 016): in-app buy/sell recording (secondary path alongside import).
  const [txnForm, setTxnForm] = useState<TransactionForm>(blankTransactionForm());
  const [txnBusy, setTxnBusy] = useState(false);
  const [txnError, setTxnError] = useState<string | null>(null);
  const [txnRejected, setTxnRejected] = useState<string[]>([]);
  const [removingTxnId, setRemovingTxnId] = useState<string | null>(null);
  // US4 (feature 014): owner selects holdings and runs the same on-request
  // sentiment report used on /sentiment, reusing the SentimentReport component.
  // Only selected holdings are ever sent (origin:"holding"); unselected ones are
  // never analyzed.
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

  const holdingsKey = useMemo(
    () => portfolio.holdings.map((holding) => holding.ticker).sort().join(','),
    [portfolio.holdings],
  );

  useEffect(() => {
    let cancelled = false;
    async function loadStatuses() {
      const query = queryFromSettings(settings);
      const pairs = await Promise.all(
        portfolio.holdings.map(async (holding) => {
          const status = await fetchApi(`/shariah/status/${holding.ticker}${query}`, ShariahStatusSchema);
          return [holding.ticker, status] as const;
        }),
      );
      if (!cancelled) {
        setStatuses(Object.fromEntries(pairs));
      }
    }
    if (portfolio.holdings.length) {
      loadStatuses().catch(() => setStatuses({}));
    }
    return () => {
      cancelled = true;
    };
  }, [portfolio.holdings, settings]);

  async function refreshQuotes() {
    if (!portfolio.holdings.length) {
      setQuotes({});
      setQuotesAsOf(null);
      return;
    }
    setQuotesLoading(true);
    setQuotesError(null);
    try {
      const response = await fetchApi('/portfolio/quotes', PortfolioQuotesResponseSchema, {
        method: 'POST',
        body: JSON.stringify({
          holdings: portfolio.holdings.map((holding) => ({
            ticker: holding.ticker,
            strategy_slug: settings.default_strategy_slug,
          })),
        }),
      });
      setQuotes(Object.fromEntries(response.quotes.map((quote) => [quote.ticker, quote])));
      setQuotesAsOf(response.data_as_of);
    } catch {
      setQuotesError('Portfolio quotes are unavailable.');
    } finally {
      setQuotesLoading(false);
    }
  }

  useEffect(() => {
    const id = window.setTimeout(() => {
      refreshQuotes();
    }, 0);
    return () => window.clearTimeout(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [holdingsKey, settings.default_strategy_slug]);

  useEffect(() => {
    function handleFocus() {
      refreshQuotes();
    }
    window.addEventListener('focus', handleFocus);
    return () => window.removeEventListener('focus', handleFocus);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [holdingsKey, settings.default_strategy_slug]);

  // Fetch the purchase-anchored levels / sizing for the imported holdings. Reads
  // the live transaction count from the store so it stays correct when invoked
  // imperatively right after a removal (the render closure may still be stale).
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
      // Feature 016 (US2): size against the cash-first effective capital and pass
      // the optional available_cash hard limit so each recommended size respects
      // the owner's cash. Absent cash ⇒ byte-identical to today.
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
  }, [portfolio.total_capital, portfolio.available_cash, holdingsKey, settings.default_strategy_slug]);

  useEffect(() => {
    // Defer out of the synchronous effect body (loadHoldings may setState
    // immediately when the ledger is empty) to avoid cascading renders.
    const id = window.setTimeout(() => {
      loadHoldings();
    }, 0);
    return () => window.clearTimeout(id);
  }, [loadHoldings, storeTransactions]);

  // Remove one ticker's imported transactions (and its derived holding). The
  // local ledger is the source of truth; we persist it immediately so the
  // holdings re-fetch reads the post-removal blob, then refresh totals/levels.
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

  const derived = useMemo(() => {
    const holdings = portfolio.holdings.map((holding) => {
      const quote = quotes[holding.ticker];
      const currentPrice = quote?.latest_price ? Number(quote.latest_price) : holding.current_price;
      const marketValue = holding.shares * currentPrice;
      const costBasis = holding.shares * holding.avg_cost;
      const liquidityExcluded =
        currentPrice < settings.liquidity_min_price ||
        (holding.avg_dollar_volume_20d !== undefined &&
          holding.avg_dollar_volume_20d < settings.liquidity_min_avg_dollar_volume_20d);
      return {
        ...holding,
        currentPrice,
        quote,
        marketValue,
        costBasis,
        unrealizedGain: marketValue - costBasis,
        positionPct: portfolio.total_capital > 0 ? marketValue / portfolio.total_capital : 0,
        liquidityExcluded,
      };
    });
    const totalInvested = holdings.reduce((sum, holding) => sum + holding.marketValue, 0);
    const cash = portfolio.cash_balance_override ?? portfolio.total_capital - totalInvested;
    const sectors = new Map<string, number>();
    for (const holding of holdings) {
      sectors.set(holding.sector, (sectors.get(holding.sector) ?? 0) + holding.marketValue);
    }
    const sectorExposure = Array.from(sectors.entries())
      .map(([sector, value]) => ({
        sector,
        value,
        percentOfCapital: portfolio.total_capital > 0 ? value / portfolio.total_capital : 0,
        overCap: portfolio.total_capital > 0 ? value / portfolio.total_capital > settings.per_sector_cap_pct : false,
      }))
      .sort((left, right) => right.value - left.value);
    const flags = [
      ...holdings
        .filter((holding) => holding.positionPct > settings.per_position_cap_pct)
        .map((holding) => `${holding.ticker} position is ${percent(holding.positionPct)}, above ${percent(settings.per_position_cap_pct)}.`),
      ...sectorExposure
        .filter((sector) => sector.overCap)
        .map((sector) => `${sector.sector} exposure is ${percent(sector.percentOfCapital)}, above ${percent(settings.per_sector_cap_pct)}.`),
    ];
    const nonCompliant = holdings.filter((holding) => statuses[holding.ticker]?.is_compliant === false).length;
    const marked = holdings.filter((holding) => {
      const symbol = holding.ticker.toUpperCase();
      return (
        settings.shariah_user_inclusion.some((entry) => entry.ticker === symbol) ||
        settings.shariah_user_exclusion.some((entry) => entry.ticker === symbol)
      );
    }).length;
    return { holdings, totalInvested, cash, sectorExposure, flags, nonCompliant, marked };
  }, [portfolio, quotes, settings, statuses]);

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

  function updateForm(field: keyof HoldingForm, value: string) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  function submitHolding(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const holding = {
      ticker: form.ticker,
      shares: Number(form.shares),
      avg_cost: Number(form.avg_cost),
      current_price: Number(form.current_price),
      sector: form.sector,
      avg_dollar_volume_20d: form.avg_dollar_volume_20d ? Number(form.avg_dollar_volume_20d) : undefined,
      note: form.note.trim() || undefined,
    };
    if (editingTicker) {
      updateHolding(editingTicker, holding);
    } else {
      addHolding(holding);
      if (portfolio.holdings.length === 0 && !portfolio.local_storage_notice_acknowledged) {
        setShowStorageWarning(true);
      }
    }
    setForm(blankForm());
    setEditingTicker(null);
  }

  function startEdit(holding: Holding) {
    setEditingTicker(holding.ticker);
    setForm(formFromHolding(holding));
  }

  function closeStorageWarning() {
    acknowledgeLocalStorageWarning();
    setShowStorageWarning(false);
  }

  // Feature 016 (US2): cash-first capital model. When available cash is set,
  // total capital derives as cash + current holdings market value (manual +
  // imported, server-priced where available; graceful when quotes are missing).
  const cashSet = portfolio.available_cash != null;
  const holdingsMarketValueDisplay =
    derived.totalInvested + (importedTotals ? Number(importedTotals.total_invested) : 0);
  const derivedTotalCapital = cashSet
    ? (portfolio.available_cash ?? 0) + holdingsMarketValueDisplay
    : portfolio.total_capital;

  return (
    <main className="mx-auto max-w-6xl space-y-6 px-6 py-8">
      <header className="border-b border-gray-200 pb-5">
        <h1 className="text-2xl font-semibold text-gray-950">{COPY.PORTFOLIO.TITLE}</h1>
        <div className="mt-2 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-sm text-gray-600">Stored locally in this browser.</p>
          <div className="flex flex-wrap items-center gap-2">
            {importedAsOf ? <AsOfBadge date={importedAsOf} /> : quotesAsOf ? <AsOfBadge date={quotesAsOf} /> : null}
            <button
              className="border border-gray-300 px-3 py-2 text-sm font-semibold text-gray-800 disabled:opacity-50"
              disabled={quotesLoading || portfolio.holdings.length === 0}
              onClick={refreshQuotes}
              type="button"
            >
              {quotesLoading ? 'Refreshing...' : 'Refresh prices'}
            </button>
          </div>
        </div>
      </header>
      {quotesError ? (
        <div className="border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">{quotesError}</div>
      ) : null}
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
          {importedTotals &&
          (importedTotals.realized_pnl != null ||
            importedTotals.unrealized_pnl != null) ? (
            <div aria-label="Portfolio profit and loss" className="grid gap-3 sm:grid-cols-4">
              <div className="border border-gray-200 p-3">
                <div className="text-xs uppercase text-gray-500">Realized P/L</div>
                <div
                  className={
                    importedTotals.realized_pnl != null && Number(importedTotals.realized_pnl) < 0
                      ? 'text-lg font-semibold text-rose-700'
                      : 'text-lg font-semibold text-emerald-700'
                  }
                >
                  {importedTotals.realized_pnl != null ? formatMoney(importedTotals.realized_pnl) : '-'}
                </div>
                {importedTotals.closed_trade_count ? (
                  <div className="mt-1 text-xs text-gray-500">
                    {importedTotals.closed_trade_count} closed trade
                    {importedTotals.closed_trade_count === 1 ? '' : 's'}
                  </div>
                ) : null}
              </div>
              <div className="border border-gray-200 p-3">
                <div className="text-xs uppercase text-gray-500">Unrealized P/L</div>
                <div
                  className={
                    importedTotals.unrealized_pnl != null && Number(importedTotals.unrealized_pnl) < 0
                      ? 'text-lg font-semibold text-rose-700'
                      : 'text-lg font-semibold text-emerald-700'
                  }
                >
                  {importedTotals.unrealized_pnl != null ? formatMoney(importedTotals.unrealized_pnl) : '-'}
                </div>
              </div>
              <div className="border border-gray-200 p-3">
                <div className="text-xs uppercase text-gray-500">Total P/L</div>
                <div
                  className={
                    importedTotals.total_pnl != null && Number(importedTotals.total_pnl) < 0
                      ? 'text-lg font-semibold text-rose-700'
                      : 'text-lg font-semibold text-emerald-700'
                  }
                >
                  {importedTotals.total_pnl != null ? formatMoney(importedTotals.total_pnl) : '-'}
                </div>
              </div>
              <div className="border border-gray-200 p-3">
                <div className="text-xs uppercase text-gray-500">Win rate</div>
                <div className="text-lg font-semibold text-gray-950">
                  {importedTotals.win_rate != null ? percent(importedTotals.win_rate) : '-'}
                </div>
                {importedTotals.win_rate != null ? (
                  <div className="mt-1 text-xs text-gray-500">
                    {importedTotals.winning_trade_count ?? 0} of {importedTotals.closed_trade_count ?? 0} closed
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
      ) : null}

      {sentimentSelections ? (
        <section aria-label="Holdings sentiment report" className="space-y-3">
          <h2 className="text-lg font-semibold text-gray-950">Holdings Sentiment Report</h2>
          <SentimentReport
            initialSelections={sentimentSelections}
            key={sentimentSelections.map((selection) => selection.ticker).join(',')}
          />
        </section>
      ) : null}

      <section className="grid gap-4 md:grid-cols-4">
        <label className="border border-gray-200 p-4 text-sm text-gray-800">
          <span className="font-medium">Available cash</span>
          <input
            aria-label="Available cash"
            className="mt-2 w-full border border-gray-300 px-3 py-2"
            min={0}
            onChange={(event) =>
              setAvailableCash(event.target.value === '' ? null : Number(event.target.value))
            }
            placeholder="Optional"
            type="number"
            value={portfolio.available_cash ?? ''}
          />
          <span className="mt-1 block text-xs text-gray-500">
            {cashSet
              ? 'Suggested sizes are limited to this cash.'
              : 'Leave blank to size against total capital.'}
          </span>
        </label>
        {cashSet ? (
          <div className="border border-gray-200 p-4">
            <div className="text-sm text-gray-500">Total capital (derived)</div>
            <div className="text-2xl font-semibold text-gray-950">{money(derivedTotalCapital)}</div>
            <div className="mt-1 text-xs text-gray-500">
              cash {money(portfolio.available_cash ?? 0)} + holdings {money(holdingsMarketValueDisplay)}
            </div>
          </div>
        ) : (
          <label className="border border-gray-200 p-4 text-sm text-gray-800">
            <span className="font-medium">Total capital</span>
            <input
              aria-label="Total capital"
              className="mt-2 w-full border border-gray-300 px-3 py-2"
              min={0}
              onChange={(event) => setTotalCapital(Number(event.target.value))}
              type="number"
              value={portfolio.total_capital}
            />
          </label>
        )}
        <div className="border border-gray-200 p-4">
          <div className="text-sm text-gray-500">Total value</div>
          <div className="text-2xl font-semibold text-gray-950">{money(derived.totalInvested)}</div>
        </div>
        <div className="border border-gray-200 p-4">
          <div className="text-sm text-gray-500">{cashSet ? 'Holdings value' : 'Cash'}</div>
          <div className="text-2xl font-semibold text-gray-950">
            {money(cashSet ? holdingsMarketValueDisplay : derived.cash)}
          </div>
        </div>
      </section>

      <section className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
        <div className="space-y-4">
          {portfolio.holdings.length === 0 ? (
            <div className="border border-gray-200 p-6 text-sm text-gray-600">{COPY.PORTFOLIO.EMPTY_STATE}</div>
          ) : (
            <>
            <div className="flex justify-end">
              <button
                className="border border-gray-300 px-3 py-2 text-sm font-semibold text-gray-800 disabled:opacity-50"
                disabled={sentimentTickers.size === 0}
                onClick={runHoldingsSentiment}
                type="button"
              >
                Run sentiment report{sentimentTickers.size ? ` (${sentimentTickers.size})` : ''}
              </button>
            </div>
            <div className="overflow-x-auto border border-gray-200">
              <table className="min-w-full text-left text-sm">
                <thead className="bg-gray-50 text-xs uppercase text-gray-500">
                  <tr>
                    <th className="px-4 py-3">Report</th>
                    <th className="px-4 py-3">Ticker</th>
                    <th className="px-4 py-3">Sector</th>
                    <th className="px-4 py-3 text-right">Shares</th>
                    <th className="px-4 py-3 text-right">Price</th>
                    <th className="px-4 py-3 text-right">Value</th>
                    <th className="px-4 py-3 text-right">Unrealized P/L</th>
                    <th className="px-4 py-3 text-right">Stop</th>
                    <th className="px-4 py-3 text-right">Target</th>
                    <th className="px-4 py-3">Status</th>
                    <th className="px-4 py-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {derived.holdings.map((holding) => (
                    <tr className="border-t border-gray-200" key={`${holding.ticker}-${holding.added_at}`}>
                      <td className="px-4 py-3">
                        <input
                          aria-label={`Select ${holding.ticker} for sentiment report`}
                          checked={sentimentTickers.has(holding.ticker)}
                          onChange={() => toggleSentimentTicker(holding.ticker)}
                          type="checkbox"
                        />
                      </td>
                      <td className="px-4 py-3 font-semibold text-gray-950">{holding.ticker}</td>
                      <td className="px-4 py-3 text-gray-700">{holding.sector}</td>
                      <td className="px-4 py-3 text-right text-gray-700">{holding.shares}</td>
                      <td className="px-4 py-3 text-right text-gray-700">{formatMoney(holding.currentPrice, holding.ticker)}</td>
                      <td className="px-4 py-3 text-right text-gray-700">{formatMoney(holding.marketValue, holding.ticker)}</td>
                      <td className={holding.unrealizedGain >= 0 ? 'px-4 py-3 text-right text-emerald-700' : 'px-4 py-3 text-right text-rose-700'}>
                        {formatMoney(holding.unrealizedGain, holding.ticker)}
                      </td>
                      <td className="px-4 py-3 text-right text-gray-700">
                        {holding.quote?.stop_loss ? formatMoney(holding.quote.stop_loss, holding.ticker) : '-'}
                        {holding.quote?.tighter_stop_loss &&
                        Number(holding.quote.tighter_stop_loss) > Number(holding.quote.stop_loss ?? 0) ? (
                          <div className="text-xs text-emerald-700">tighter {formatMoney(holding.quote.tighter_stop_loss, holding.ticker)}</div>
                        ) : null}
                      </td>
                      <td className="px-4 py-3 text-right text-gray-700">
                        {holding.quote?.take_profit ? formatMoney(holding.quote.take_profit, holding.ticker) : '-'}
                      </td>
                      <td className="space-y-2 px-4 py-3">
                        <ShariahBadge status={statuses[holding.ticker]} />
                        {holding.quote?.is_stale ? (
                          <span className="block border border-amber-300 bg-amber-50 px-2 py-1 text-xs font-medium text-amber-800">
                            Stale quote
                          </span>
                        ) : null}
                        {holding.liquidityExcluded ? (
                          <span className="block border border-amber-300 bg-amber-50 px-2 py-1 text-xs font-medium text-amber-800">
                            Excluded by liquidity gate
                          </span>
                        ) : null}
                      </td>
                      <td className="space-x-2 px-4 py-3 text-right">
                        <button
                          className="border border-gray-300 px-3 py-1 text-xs font-medium text-gray-800 hover:bg-gray-50"
                          onClick={() => startEdit(holding)}
                          type="button"
                        >
                          Edit
                        </button>
                        <button
                          className="border border-gray-300 px-3 py-1 text-xs font-medium text-gray-800 hover:bg-gray-50"
                          onClick={() => removeHolding(holding.ticker)}
                          type="button"
                        >
                          Remove
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            </>
          )}

          <section className="grid gap-4 md:grid-cols-2">
            <div className="border border-gray-200 p-4">
              <div className="text-sm text-gray-500">Non-compliant count</div>
              <div className="text-2xl font-semibold text-gray-950">{derived.nonCompliant}</div>
            </div>
            <div className="border border-gray-200 p-4">
              <div className="text-sm text-gray-500">Concentration flags</div>
              {derived.flags.length === 0 ? (
                <div className="mt-2 text-sm text-gray-600">No cap flags.</div>
              ) : (
                <ul className="mt-2 space-y-2 text-sm text-amber-900">
                  {derived.flags.map((flag) => (
                    <li className="border border-amber-300 bg-amber-50 p-2" key={flag}>
                      {flag}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </section>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold text-gray-950">Sector Exposure</h2>
        <PortfolioAllocationChart sectors={derived.sectorExposure} capPct={settings.per_sector_cap_pct} />
        {derived.sectorExposure.length === 0 ? (
          <div className="text-sm text-gray-600">No sector exposure yet.</div>
        ) : (
              <div className="space-y-3">
                {derived.sectorExposure.map((sector) => (
                  <div key={sector.sector}>
                    <div className="mb-1 flex items-center justify-between gap-3 text-sm">
                      <span className="font-medium text-gray-900">{sector.sector}</span>
                      <span className={sector.overCap ? 'text-amber-900' : 'text-gray-600'}>
                        {money(sector.value)} - {percent(sector.percentOfCapital)}
                      </span>
                    </div>
                    <div className="h-2 bg-gray-100">
                      <div
                        className={sector.overCap ? 'h-2 bg-amber-500' : 'h-2 bg-gray-900'}
                        style={{ width: `${Math.min(100, sector.percentOfCapital * 100)}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>
        </div>

        <form className="space-y-4 border border-gray-200 p-5" onSubmit={submitHolding}>
          <h2 className="text-lg font-semibold text-gray-950">{editingTicker ? 'Edit Holding' : 'Add Holding'}</h2>
          <label className="block text-sm text-gray-800">
            <span className="font-medium">Holding ticker</span>
            <input
              aria-label="Holding ticker"
              className="mt-1 w-full border border-gray-300 px-3 py-2 uppercase"
              onChange={(event) => updateForm('ticker', event.target.value)}
              required
              value={form.ticker}
            />
          </label>
          <label className="block text-sm text-gray-800">
            <span className="font-medium">Shares</span>
            <input
              aria-label="Shares"
              className="mt-1 w-full border border-gray-300 px-3 py-2"
              min={0}
              onChange={(event) => updateForm('shares', event.target.value)}
              required
              step={0.0001}
              type="number"
              value={form.shares}
            />
          </label>
          <label className="block text-sm text-gray-800">
            <span className="font-medium">Average cost</span>
            <input
              aria-label="Average cost"
              className="mt-1 w-full border border-gray-300 px-3 py-2"
              min={0}
              onChange={(event) => updateForm('avg_cost', event.target.value)}
              required
              step={0.01}
              type="number"
              value={form.avg_cost}
            />
          </label>
          <label className="block text-sm text-gray-800">
            <span className="font-medium">Current price</span>
            <input
              aria-label="Current price"
              className="mt-1 w-full border border-gray-300 px-3 py-2"
              min={0}
              onChange={(event) => updateForm('current_price', event.target.value)}
              required
              step={0.01}
              type="number"
              value={form.current_price}
            />
          </label>
          <label className="block text-sm text-gray-800">
            <span className="font-medium">Sector</span>
            <select
              aria-label="Sector"
              className="mt-1 w-full border border-gray-300 px-3 py-2"
              onChange={(event) => updateForm('sector', event.target.value)}
              value={form.sector}
            >
              {SECTORS.map((sector) => (
                <option key={sector} value={sector}>
                  {sector}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-sm text-gray-800">
            <span className="font-medium">20-day dollar volume</span>
            <input
              aria-label="20-day dollar volume"
              className="mt-1 w-full border border-gray-300 px-3 py-2"
              min={0}
              onChange={(event) => updateForm('avg_dollar_volume_20d', event.target.value)}
              step={1000}
              type="number"
              value={form.avg_dollar_volume_20d}
            />
          </label>
          <label className="block text-sm text-gray-800">
            <span className="font-medium">Note</span>
            <input
              aria-label="Note"
              className="mt-1 w-full border border-gray-300 px-3 py-2"
              onChange={(event) => updateForm('note', event.target.value)}
              value={form.note}
            />
          </label>
          <div className="flex flex-wrap gap-2">
            <button className="border border-gray-950 bg-gray-950 px-4 py-2 text-sm font-semibold text-white" type="submit">
              {editingTicker ? 'Save holding' : 'Add holding'}
            </button>
            {editingTicker ? (
              <button
                className="border border-gray-300 px-4 py-2 text-sm font-semibold text-gray-800"
                onClick={() => {
                  setEditingTicker(null);
                  setForm(blankForm());
                }}
                type="button"
              >
                Cancel
              </button>
            ) : null}
          </div>
        </form>
      </section>

      {showStorageWarning ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 px-4">
          <div className="max-w-md border border-gray-300 bg-white p-6 shadow-xl" role="dialog" aria-modal="true">
            <h2 className="text-lg font-semibold text-gray-950">Holdings are stored locally on this device</h2>
            <p className="mt-2 text-sm text-gray-600">
              Portfolio data stays in this browser&apos;s local storage. Use Settings export/import when moving devices or clearing browser data.
            </p>
            <button
              className="mt-4 border border-gray-950 bg-gray-950 px-4 py-2 text-sm font-semibold text-white"
              onClick={closeStorageWarning}
              type="button"
            >
              I understand
            </button>
          </div>
        </div>
      ) : null}
    </main>
  );
}
