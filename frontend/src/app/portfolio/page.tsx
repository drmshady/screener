"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from 'react';
import { AsOfBadge } from '@/components/AsOfBadge';
import { ImportTransactions } from '@/components/ImportTransactions';
import { PortfolioAllocationChart } from '@/components/ChartPanels';
import { ShariahBadge } from '@/components/ShariahBadge';
import {
  ImportResult,
  LevelBlock,
  PortfolioQuote,
  PortfolioHoldingWithLevels,
  PortfolioQuotesResponseSchema,
  ShariahStatus,
  ShariahStatusSchema,
  fetchApi,
  fetchHoldings,
  getPortfolioState,
} from '@/lib/api';
import { COPY } from '@/lib/copy';
import { formatMoney } from '@/lib/format';
import { Holding, Transaction, useAppStore } from '@/lib/store';

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

function levelStatusLabel(status: LevelBlock['status']) {
  if (status === 'stop_breached') return 'Stop breached';
  if (status === 'target_reached') return 'Target reached';
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
      <div className="text-xs text-gray-500">
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
  const addHolding = useAppStore((state) => state.addHolding);
  const updateHolding = useAppStore((state) => state.updateHolding);
  const removeHolding = useAppStore((state) => state.removeHolding);
  const acknowledgeLocalStorageWarning = useAppStore((state) => state.acknowledgeLocalStorageWarning);
  const setTransactions = useAppStore((s) => s.setTransactions);
  const storeTransactions = useAppStore((s) => s.transactions);
  const storeSheetId = useAppStore((s) => s.sheet_id);
  const storeSheetRange = useAppStore((s) => s.sheet_range);

  const importedHoldings = useMemo(
    () => computeImportedHoldings(storeTransactions),
    [storeTransactions],
  );

  // After a successful import, re-fetch the server blob to sync transactions into the store.
  const handleImported = useCallback(
    async (_result: ImportResult) => {
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
        // Backend unreachable — the store already has the pre-import data
      }
    },
    [setTransactions],
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
  } | null>(null);
  const [importedDetailsLoading, setImportedDetailsLoading] = useState(false);
  const [importedDetailsError, setImportedDetailsError] = useState<string | null>(null);
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

  useEffect(() => {
    let cancelled = false;
    async function loadImportedDetails() {
      if (!storeTransactions.length) {
        setImportedDetails({});
        setImportedAsOf(null);
        setImportedTotals(null);
        return;
      }
      setImportedDetailsLoading(true);
      setImportedDetailsError(null);
      try {
        const response = await fetchHoldings({
          total_capital: String(portfolio.total_capital || 1),
          strategy_slug: settings.default_strategy_slug,
        });
        if (!cancelled) {
          setImportedDetails(Object.fromEntries(response.holdings.map((holding) => [holding.ticker, holding])));
          setImportedAsOf(response.data_as_of);
          setImportedTotals(response.totals);
        }
      } catch {
        if (!cancelled) {
          setImportedDetailsError('Imported holding levels are unavailable.');
        }
      } finally {
        if (!cancelled) {
          setImportedDetailsLoading(false);
        }
      }
    }
    loadImportedDetails();
    return () => {
      cancelled = true;
    };
  }, [storeTransactions, portfolio.total_capital, settings.default_strategy_slug]);

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

      {importedHoldings.length > 0 ? (
        <section aria-label="Imported holdings ledger" className="space-y-3">
          <h2 className="text-lg font-semibold text-gray-950">Imported Holdings</h2>
          <p className="text-xs text-gray-500">
            Derived from {storeTransactions.length} imported transaction{storeTransactions.length !== 1 ? 's' : ''}.
            {importedDetailsLoading ? ' Level details are refreshing.' : ' Level details are recomputed from the latest snapshot.'}
          </p>
          {importedTotals ? (
            <div className="grid gap-3 sm:grid-cols-3">
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
            </div>
          ) : null}
          <div className="overflow-x-auto border border-gray-200">
            <table className="min-w-full text-left text-sm">
              <thead className="bg-gray-50 text-xs uppercase text-gray-500">
                <tr>
                  <th className="px-4 py-3">Ticker</th>
                  <th className="px-4 py-3 text-right">Net shares</th>
                  <th className="px-4 py-3 text-right">Avg cost</th>
                  <th className="px-4 py-3">First purchase</th>
                  <th className="px-4 py-3">Latest purchase</th>
                  <th className="px-4 py-3 text-right">Current price</th>
                  <th className="px-4 py-3 text-right">Unrealized P/L</th>
                  <th className="px-4 py-3">Original plan</th>
                  <th className="px-4 py-3">Current condition</th>
                  <th className="px-4 py-3">Sizing & risk</th>
                  <th className="px-4 py-3">Status</th>
                </tr>
              </thead>
              <tbody>
                {importedHoldings.map((h) => {
                  const detail = importedDetails[h.ticker];
                  return (
                    <tr className="border-t border-gray-200" key={h.ticker}>
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
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}

      <section className="grid gap-4 md:grid-cols-4">
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
        <div className="border border-gray-200 p-4">
          <div className="text-sm text-gray-500">Total value</div>
          <div className="text-2xl font-semibold text-gray-950">{money(derived.totalInvested)}</div>
        </div>
        <div className="border border-gray-200 p-4">
          <div className="text-sm text-gray-500">Cash</div>
          <div className="text-2xl font-semibold text-gray-950">{money(derived.cash)}</div>
        </div>
        <div className="border border-gray-200 p-4">
          <div className="text-sm text-gray-500">User-marked count</div>
          <div className="text-2xl font-semibold text-gray-950">{derived.marked}</div>
        </div>
      </section>

      <section className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
        <div className="space-y-4">
          {portfolio.holdings.length === 0 ? (
            <div className="border border-gray-200 p-6 text-sm text-gray-600">{COPY.PORTFOLIO.EMPTY_STATE}</div>
          ) : (
            <div className="overflow-x-auto border border-gray-200">
              <table className="min-w-full text-left text-sm">
                <thead className="bg-gray-50 text-xs uppercase text-gray-500">
                  <tr>
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
