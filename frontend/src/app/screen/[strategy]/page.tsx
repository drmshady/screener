"use client";

import { use, useEffect, useState } from 'react';
import { AsOfBadge } from '@/components/AsOfBadge';
import { CandidateRow } from '@/components/CandidateRow';
import { CopyScreenAdvisorPrompt } from '@/components/CopyScreenAdvisorPrompt';
import { supportsAdvisorPrompt } from '@/lib/advisorPrompt';
import { EquityCurveCharts } from '@/components/ChartPanels';
import { StrategyGatesPanel } from '@/components/StrategyGatesPanel';
import { WalkForwardMetricsPanel } from '@/components/WalkForwardMetricsPanel';
import {
  BacktestResponse,
  BacktestResponseSchema,
  EquityCurveResponse,
  EquityCurveResponseSchema,
  ScreenResult,
  ScreenResultSchema,
  Strategy,
  StrategySchema,
  ApiError,
  fetchApi,
  refreshData,
} from '@/lib/api';
import { COPY } from '@/lib/copy';
import { getCachedScreen, setCachedScreen } from '@/lib/screenCache';
import { useAppStore } from '@/lib/store';

export default function StrategyScreenPage({ params }: { params: Promise<{ strategy: string }> }) {
  const { strategy: strategySlug } = use(params);
  const cached = getCachedScreen(strategySlug);
  const [strategy, setStrategy] = useState<Strategy | null>(null);
  const [backtest, setBacktest] = useState<BacktestResponse | null>(null);
  const [equityCurve, setEquityCurve] = useState<EquityCurveResponse | null>(null);
  // Restore the last run from the in-memory cache so Back from a candidate detail
  // page shows the prior results instead of forcing a fresh (slow) screen.
  const [screenResult, setScreenResult] = useState<ScreenResult | null>(cached?.result ?? null);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [runError, setRunError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [refreshNote, setRefreshNote] = useState<string | null>(null);
  const [market, setMarket] = useState<'US' | 'SA'>(cached?.market ?? 'US');
  const [showAllMatches, setShowAllMatches] = useState(false);
  const [excludeEarningsOverride, setExcludeEarningsOverride] = useState<boolean | null>(null);
  const [earningsWindowOverride, setEarningsWindowOverride] = useState<number | null>(null);
  // Sector-strength (industry-momentum) gate: off by default (lost the A/B on
  // returns); when on, keep only names in the top half of sectors by breadth.
  // This is a momentum overlay, so the control only renders for that strategy.
  const [sectorGateOn, setSectorGateOn] = useState(false);
  const [entryReadyOnly, setEntryReadyOnly] = useState(false);
  // Expanded coverage (US2): off by default (today's strict gating). When on,
  // momentum candidates failing a non-essential (preferred) gate are retained,
  // marked skipped, and demoted below all clean names.
  const [expandedCoverage, setExpandedCoverage] = useState(false);
  // Value-only falling-knife guard: off by default (pure value). When on, exclude
  // names whose 12-1 month momentum is below the floor so the screen doesn't buy
  // cheapness that is cheap *because* it is collapsing.
  const [momentumFloorOn, setMomentumFloorOn] = useState(false);
  const settings = useAppStore((state) => state.settings);
  const isMomentum = strategySlug === 'midterm_52w_high_momentum';
  const isValue = strategySlug === 'midterm_value_composite';
  // Floor applied when the value momentum guard is on; <= -1.0 means disabled.
  const VALUE_MOMENTUM_FLOOR = -0.2;

  useEffect(() => {
    fetchApi(`/strategies/${strategySlug}`, StrategySchema)
      .then((payload) => {
        setStrategy(payload);
        setLoadError(null);
      })
      .catch((error) =>
        setLoadError(error instanceof Error ? error.message : 'Strategy metadata unavailable.'),
      );
    fetchApi(`/strategies/${strategySlug}/backtest`, BacktestResponseSchema)
      .then((payload) => {
        setBacktest(payload);
        setLoadError(null);
      })
      .catch((error) =>
        setLoadError(
          error instanceof Error
            ? `Backtest unavailable: ${error.message}`
            : 'Backtest unavailable. Retry when the backend is available.',
        ),
      );
    fetchApi(`/strategies/${strategySlug}/backtest/equity-curve`, EquityCurveResponseSchema)
      .then(setEquityCurve)
      .catch(() => setEquityCurve(null));
  }, [strategySlug]);

  function buildRequestBody() {
    const configuredEarningsWindow =
      settings.exclude_earnings_within_days_overrides[strategySlug] ??
      strategy?.default_exclude_earnings_within_days ??
      0;
    const effectiveEarningsWindow = earningsWindowOverride ?? configuredEarningsWindow;
    const effectiveExcludeEarnings = excludeEarningsOverride ?? configuredEarningsWindow > 0;
    const isSaudi = market === 'SA';
    // 1.0 disables the sector-strength gate; 0.5 keeps the top half of sectors.
    const sectorFraction = sectorGateOn ? 0.5 : 1.0;
    // Value-only: <= -1.0 disables the 12-1 momentum floor (pure value).
    const valueParams = isValue
      ? { min_momentum_12_1: momentumFloorOn ? VALUE_MOMENTUM_FLOOR : -1.0 }
      : {};
    const entryParams = isMomentum
      ? { entry_ready_only: entryReadyOnly, expanded_coverage: expandedCoverage }
      : {};
    return {
      parameters: isSaudi
        ? { market: 'SA', sector_strength_top_fraction: sectorFraction, ...entryParams, ...valueParams }
        : {
            liquidity_min_avg_dollar_volume_20d: settings.liquidity_min_avg_dollar_volume_20d,
            liquidity_min_price: settings.liquidity_min_price,
            sector_strength_top_fraction: sectorFraction,
            ...entryParams,
            ...valueParams,
          },
      filters: {
        // Saudi compliance data is test-only, so don't apply the Shariah gate there.
        shariah_only: !isSaudi && settings.shariah_filter_on && !showAllMatches,
        exclude_earnings_within_days: effectiveExcludeEarnings ? effectiveEarningsWindow : 0,
      },
      shariah_overrides: {
        active_sources: settings.shariah_external_sources,
        inclusion: settings.shariah_user_inclusion,
        exclusion: settings.shariah_user_exclusion,
      },
    };
  }

  async function handleRun() {
    setLoading(true);
    setRunError(null);
    try {
      const result = await fetchApi(`/strategies/${strategySlug}/run`, ScreenResultSchema, {
        method: 'POST',
        body: JSON.stringify(buildRequestBody()),
      });
      setScreenResult(result);
      // Cache so navigating into a candidate detail and back doesn't re-run.
      setCachedScreen(strategySlug, { result, market, ranAt: Date.now() });
    } catch (error) {
      const retry = error instanceof ApiError && error.retryable ? ' Retry when the backend is available.' : '';
      setRunError(
        error instanceof Error
          ? `${error.message}${retry}`
          : 'The screen could not be run. Retry when the backend is available.',
      );
    } finally {
      setLoading(false);
    }
  }

  async function handleRefresh() {
    setRefreshing(true);
    setRefreshNote(null);
    try {
      const r = await refreshData(market);
      setRefreshNote(
        `Updated ${r.refreshed_tickers} ${market === 'SA' ? 'Saudi' : 'US'} names` +
          ` — latest bar ${r.latest_bar ?? 'n/a'} (${r.fetched_rows} new rows). Re-running...`,
      );
      await handleRun();
    } catch {
      setRefreshNote('Data update failed — the backend may be unreachable.');
    } finally {
      setRefreshing(false);
    }
  }

  if (!strategy && !loadError) {
    return <main className="mx-auto max-w-6xl px-6 py-8 text-sm text-slate-600">Loading strategy...</main>;
  }

  if (!strategy) {
    return (
      <main className="mx-auto max-w-6xl space-y-4 px-6 py-8 text-sm text-slate-600">
        <h1 className="text-xl font-semibold text-slate-950">Strategy unavailable</h1>
        <p>{loadError ?? 'Strategy metadata could not be loaded.'}</p>
      </main>
    );
  }

  const configuredEarningsWindow =
    settings.exclude_earnings_within_days_overrides[strategySlug] ??
    strategy.default_exclude_earnings_within_days;
  const effectiveEarningsWindow = earningsWindowOverride ?? configuredEarningsWindow;
  const effectiveExcludeEarnings = excludeEarningsOverride ?? configuredEarningsWindow > 0;

  return (
    <main className="mx-auto max-w-7xl space-y-8 px-4 py-6 sm:px-6 lg:px-8">
      <header className="flex flex-col gap-4 border-b border-slate-200 pb-5 sm:flex-row sm:items-end sm:justify-between">
        <div className="space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-2xl font-semibold tracking-normal text-slate-950">{strategy.name}</h1>
            <span className="border border-slate-300 px-2 py-1 text-xs text-slate-700">{strategy.timeframe}</span>
          </div>
          <p className="max-w-3xl text-sm text-slate-600">{strategy.description}</p>
          {backtest ? (
            <AsOfBadge date={backtest.data_as_of} sourceName={backtest.data_sources[0]?.source_name} />
          ) : null}
        </div>
        <div className="flex flex-col items-stretch gap-2 sm:items-end">
          <div className="inline-flex overflow-hidden border border-slate-300 text-sm">
            <button
              type="button"
              className={`px-3 py-1.5 font-medium ${market === 'US' ? 'bg-slate-950 text-white' : 'bg-white text-slate-700 hover:bg-slate-100'}`}
              onClick={() => setMarket('US')}
            >
              US
            </button>
            <button
              type="button"
              className={`px-3 py-1.5 font-medium ${market === 'SA' ? 'bg-slate-950 text-white' : 'bg-white text-slate-700 hover:bg-slate-100'}`}
              onClick={() => setMarket('SA')}
            >
              Saudi (test)
            </button>
          </div>
          <div className="flex gap-2">
            <button
              type="button"
              className="border border-slate-300 px-3 py-2 text-sm font-medium text-slate-800 hover:bg-slate-100 disabled:opacity-50"
              disabled={refreshing || loading}
              onClick={handleRefresh}
              title="Fetch the latest prices for this market, then re-run"
            >
              {refreshing ? 'Updating...' : 'Update data'}
            </button>
            <button
              type="button"
              className="border border-slate-950 bg-slate-950 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-800 disabled:opacity-50"
              disabled={loading}
              onClick={handleRun}
            >
              {loading ? 'Running...' : COPY.SCREENER.RUN_SCREEN}
            </button>
          </div>
          {refreshNote ? <p className="text-xs text-slate-500 sm:text-right">{refreshNote}</p> : null}
        </div>
      </header>

      {market === 'SA' ? (
        <section className="border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
          Saudi (Tadawul) is a test market: prices in SAR via yfinance `.SR`, the SPY-based regime gate
          is off, and the Shariah filter is not applied (Saudi compliance data is unverified test-only).
        </section>
      ) : null}

      <section className="panel flex flex-col gap-3 p-4 text-sm text-slate-700 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="font-medium text-slate-950">Shariah filter</div>
          <div>
            {settings.shariah_filter_on ? 'On' : 'Off'} - sources: {settings.shariah_external_sources.join(', ') || 'none'}
          </div>
        </div>
        {settings.shariah_filter_on ? (
          <label className="inline-flex items-center gap-2">
            <input
              checked={showAllMatches}
              className="h-4 w-4"
              onChange={(event) => setShowAllMatches(event.target.checked)}
              type="checkbox"
            />
            <span>Show all matches for this run</span>
          </label>
        ) : null}
      </section>

      <section className="panel flex flex-col gap-3 p-4 text-sm text-slate-700 sm:flex-row sm:items-center sm:justify-between">
        <label className="inline-flex items-center gap-2">
          <input
            checked={effectiveExcludeEarnings}
            className="h-4 w-4"
            onChange={(event) => setExcludeEarningsOverride(event.target.checked)}
            type="checkbox"
          />
          <span>Exclude earnings within</span>
        </label>
        <input
          aria-label="Earnings exclusion days"
          className="w-28 border border-slate-300 px-3 py-2"
          disabled={!effectiveExcludeEarnings}
          min={0}
          onChange={(event) => setEarningsWindowOverride(Number(event.target.value))}
          type="number"
          value={effectiveEarningsWindow}
        />
      </section>

      {isMomentum ? (
        <section className="panel flex flex-col gap-3 p-4 text-sm text-slate-700">
          <label className="inline-flex items-center gap-2">
            <input
              checked={sectorGateOn}
              className="h-4 w-4"
              onChange={(event) => setSectorGateOn(event.target.checked)}
              type="checkbox"
            />
            <span className="font-medium text-slate-900">Sector-strength gate (industry momentum)</span>
          </label>
          <p className="text-xs text-slate-500 sm:pl-6">
            {sectorGateOn
              ? 'On: keep only names in the top half of sectors by breadth (lower drawdown, fewer candidates).'
              : 'Off (default): the gate lost the A/B on returns, so it is disabled. Turn on to filter to leading sectors.'}
          </p>
          <label className="inline-flex items-center gap-2">
            <input
              checked={entryReadyOnly}
              className="h-4 w-4"
              onChange={(event) => setEntryReadyOnly(event.target.checked)}
              type="checkbox"
            />
            <span className="font-medium text-slate-900">Entry-ready only</span>
          </label>
          <p className="text-xs text-slate-500 sm:pl-6">
            {entryReadyOnly
              ? 'On: show only names whose entry-timing diagnostics are all passing.'
              : 'Off (default): annotate every returned momentum candidate.'}
          </p>
          <label className="inline-flex items-center gap-2">
            <input
              checked={expandedCoverage}
              className="h-4 w-4"
              onChange={(event) => setExpandedCoverage(event.target.checked)}
              type="checkbox"
            />
            <span className="font-medium text-slate-900">Expanded coverage</span>
          </label>
          <p className="text-xs text-slate-500 sm:pl-6">
            {expandedCoverage
              ? 'On: keep names that miss a non-essential (preferred) gate — they are marked skipped, with the reason, and ranked below every clean name. Essential gates and disqualifiers still exclude.'
              : 'Off (default): strict gating — a name failing any gate is dropped. No gate threshold changes either way.'}
          </p>
        </section>
      ) : null}

      {isValue ? (
        <section className="panel flex flex-col gap-1 p-4 text-sm text-slate-700">
          <label className="inline-flex items-center gap-2">
            <input
              checked={momentumFloorOn}
              className="h-4 w-4"
              onChange={(event) => setMomentumFloorOn(event.target.checked)}
              type="checkbox"
            />
            <span className="font-medium text-slate-900">Falling-knife guard (12-1 momentum floor)</span>
          </label>
          <p className="text-xs text-slate-500 sm:pl-6">
            {momentumFloorOn
              ? `On: exclude names whose 12-1 month momentum is below ${Math.round(VALUE_MOMENTUM_FLOOR * 100)}% — drops cheapness that is cheap because it is collapsing. Names with unknown momentum pass through.`
              : 'Off (default): pure value. The Piotroski gate screens financial health, not price trend, so deep decliners can pass. Turn on to also require the price not be in a steep downtrend.'}
          </p>
        </section>
      ) : null}

      {runError ? (
        <section className="border border-red-200 bg-red-50 p-4 text-sm text-red-900" role="alert">
          <p className="font-medium">Screen run failed.</p>
          <p className="mt-1">{runError}</p>
        </section>
      ) : null}

      {screenResult?.regime ? (
        <section
          className={`border p-4 text-sm ${
            screenResult.regime_allows_new_entries === false
              ? 'border-amber-300 bg-amber-50 text-amber-900'
              : 'border-slate-200 bg-slate-50 text-slate-700'
          }`}
        >
          <span className="font-medium">Market regime: {screenResult.regime}.</span>{' '}
          {screenResult.regime_note}
          {screenResult.regime_allows_new_entries === false
            ? ' Regime gate is closed while the market is below its 200-day trend.'
            : ''}
        </section>
      ) : null}

      {screenResult ? (
        <section className="space-y-3">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h2 className="text-lg font-semibold text-slate-950">Candidates</h2>
              <p className="text-sm text-slate-600">
                {screenResult.candidate_count} matches for {screenResult.as_of_date}
              </p>
            </div>
            <div className="flex flex-col items-stretch gap-2 sm:items-end">
              <AsOfBadge date={screenResult.data_as_of} />
              {supportsAdvisorPrompt(strategySlug) && screenResult.candidates.length > 0 ? (
                <div className="flex flex-col items-stretch gap-2 sm:items-end">
                  <CopyScreenAdvisorPrompt slug={strategySlug} getRequestBody={buildRequestBody} disabled={loading} />
                  {isMomentum ? (
                    <>
                      <CopyScreenAdvisorPrompt
                        slug={strategySlug}
                        getRequestBody={buildRequestBody}
                        disabled={loading}
                        overrideParameters={{ expanded_coverage: true, entry_ready_only: false }}
                        idleLabel="Copy Project triage prompt (Enter / Watch)"
                      />
                      <p className="max-w-xs text-right text-xs text-slate-500">
                        One click: runs the wider expanded-coverage list and copies an Enter / Watch
                        prompt ready to paste into the Claude Project.
                      </p>
                    </>
                  ) : null}
                </div>
              ) : null}
            </div>
          </div>
          {screenResult.stale_sources?.length ? (
            <div className="border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
              Shariah source warning: {screenResult.stale_sources.join(', ')}
            </div>
          ) : null}
          {screenResult.data_notes?.length ? (
            <div className="border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
              <p className="font-medium">Data completeness</p>
              <ul className="mt-1 list-disc pl-5">
                {screenResult.data_notes.map((note) => (
                  <li key={note}>{note}</li>
                ))}
              </ul>
            </div>
          ) : null}
          {screenResult.candidates.length === 0 ? (
            <div className="border border-slate-200 bg-white p-4 text-sm text-slate-600">
              <p className="font-medium text-slate-950">
                {isMomentum && entryReadyOnly
                  ? 'No candidates are entry-ready under the active diagnostics.'
                  : 'No candidates matched the active filters.'}
              </p>
              <p className="mt-1">
                Review the data completeness notes, adjust filters, or refresh stale sources before interpreting the
                screen.
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto border border-slate-200 bg-white">
              <table className="data-table data-table--wide">
                <thead>
                  <tr>
                    <th className="px-4 py-3">Ticker</th>
                    <th className="px-4 py-3">Sector</th>
                    <th className="px-4 py-3">Shariah</th>
                    <th className="px-4 py-3 text-right">Current</th>
                    <th className="px-4 py-3 text-right">Entry</th>
                    <th className="px-4 py-3 text-right">Stop / Distance</th>
                    <th className="px-4 py-3 text-right">Target</th>
                    <th className="px-4 py-3">Reason</th>
                    <th className="px-4 py-3">Entry timing</th>
                    <th className="px-4 py-3">Events</th>
                    <th className="px-4 py-3 text-right">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {screenResult.candidates.map((candidate) => (
                    <CandidateRow
                      candidate={candidate}
                      key={candidate.ticker}
                      strategySlug={strategySlug}
                      timeframe={strategy.timeframe}
                      sectorTopFraction={sectorGateOn ? 0.5 : 1.0}
                    />
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      ) : null}

      <section className="space-y-8 border-t border-slate-200 pt-8">
        <h2 className="text-lg font-semibold text-slate-950">Strategy & backtest evidence</h2>
        {loadError ? (
          <section className="border border-amber-300 bg-amber-50 p-4 text-sm text-amber-900">
            <p className="font-medium">Backtest evidence is temporarily unavailable.</p>
            <p className="mt-1">{loadError}</p>
          </section>
        ) : null}

        <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_minmax(360px,0.8fr)]">
          <StrategyGatesPanel strategy={strategy} />
          {backtest ? (
            <WalkForwardMetricsPanel backtest={backtest} />
          ) : (
            <section className="panel p-4 text-sm text-slate-600">
              Backtest metrics are unavailable. The rest of the screen remains usable.
            </section>
          )}
        </div>

        {backtest ? <EquityCurveCharts backtest={backtest} curve={equityCurve} /> : null}
      </section>
    </main>
  );
}
