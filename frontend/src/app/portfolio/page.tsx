"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { AsOfBadge } from '@/components/AsOfBadge';
import { PortfolioAllocationChart } from '@/components/ChartPanels';
import { PositionCard } from '@/components/PositionCard';
import { RealizedSummary } from '@/components/RealizedSummary';
import { SentimentReport } from '@/components/SentimentReport';
import { ShariahBadge } from '@/components/ShariahBadge';
import {
  PortfolioQuote,
  PortfolioHoldingWithLevels,
  PortfolioQuotesResponseSchema,
  SentimentSelection,
  ShariahStatus,
  ShariahStatusSchema,
  fetchApi,
  fetchHoldings,
} from '@/lib/api';
import { COPY } from '@/lib/copy';
import { formatMoney } from '@/lib/format';
import { computeImportedHoldings } from '@/lib/importedHoldings';
import { Holding, effectiveTotalCapital, useAppStore } from '@/lib/store';

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
  const storeTransactions = useAppStore((s) => s.transactions);

  const importedHoldings = useMemo(
    () => computeImportedHoldings(storeTransactions),
    [storeTransactions],
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
  // Feature 019 (US1): whether the single-owner carve-out is active (drives
  // whether cards show the Hold/Trim/Sell verb) + the response disclaimer.
  const [directiveEnabled, setDirectiveEnabled] = useState(false);
  const [importedDisclaimer, setImportedDisclaimer] = useState<string | null>(null);
  const [importedDetailsError, setImportedDetailsError] = useState<string | null>(null);
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
      setDirectiveEnabled(false);
      setImportedDisclaimer(null);
      return;
    }
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
      setDirectiveEnabled(response.directive_enabled ?? false);
      setImportedDisclaimer(response.disclaimer);
    } catch {
      setImportedDetailsError('Imported holding levels are unavailable.');
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

  // Feature 019 (US1): the decision-surface cards render for open positions only
  // (net_quantity > 0 ⇒ status 'open'); closed positions produce no card (US3).
  const openPositionCards = useMemo(
    () =>
      importedHoldings
        .filter((h) => h.status === 'open')
        .map((h) => importedDetails[h.ticker])
        .filter((detail): detail is PortfolioHoldingWithLevels => !!detail),
    [importedHoldings, importedDetails],
  );

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
      {/* Feature 019 (US1) — Position cards: the at-a-glance decision surface */}
      {/* ------------------------------------------------------------------ */}
      {openPositionCards.length > 0 ? (
        <section aria-label="Position cards" className="space-y-3">
          <h2 className="text-lg font-semibold text-gray-950">Positions</h2>
          <div className="grid gap-4 md:grid-cols-2">
            {openPositionCards.map((detail) => (
              <PositionCard
                key={detail.ticker}
                holding={detail}
                directiveEnabled={directiveEnabled}
                dataAsOf={importedAsOf}
                disclaimer={importedDisclaimer ?? COPY.GLOBAL.DISCLAIMER}
              />
            ))}
          </div>
        </section>
      ) : null}

      {/* ------------------------------------------------------------------ */}
      {/* Feature 019 (US4) — Realized win/loss scoreboard                    */}
      {/* ------------------------------------------------------------------ */}
      <RealizedSummary
        totals={importedTotals}
        dataAsOf={importedAsOf}
        disclaimer={importedDisclaimer ?? COPY.GLOBAL.DISCLAIMER}
      />

      {/* ------------------------------------------------------------------ */}
      {/* Feature 019 (US2) — Transactions moved to their own page            */}
      {/* ------------------------------------------------------------------ */}
      <section
        aria-label="Transactions link"
        className="flex flex-col gap-3 border border-gray-200 bg-white p-4 sm:flex-row sm:items-center sm:justify-between"
      >
        <p className="text-sm text-gray-600">
          Record buys and sells, import from Google Sheets, and review your full transaction ledger
          on the Transactions page.
        </p>
        <Link
          className="whitespace-nowrap border border-gray-950 bg-gray-950 px-4 py-2 text-center text-sm font-semibold text-white"
          href="/transactions"
        >
          Go to Transactions
        </Link>
      </section>

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
