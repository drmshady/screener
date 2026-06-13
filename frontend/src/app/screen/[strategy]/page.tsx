"use client";

import { use, useEffect, useState } from 'react';
import { AsOfBadge } from '@/components/AsOfBadge';
import { CandidateRow } from '@/components/CandidateRow';
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
  const [refreshing, setRefreshing] = useState(false);
  const [refreshNote, setRefreshNote] = useState<string | null>(null);
  const [market, setMarket] = useState<'US' | 'SA'>(cached?.market ?? 'US');
  const [showAllMatches, setShowAllMatches] = useState(false);
  const [excludeEarningsOverride, setExcludeEarningsOverride] = useState<boolean | null>(null);
  const [earningsWindowOverride, setEarningsWindowOverride] = useState<number | null>(null);
  const settings = useAppStore((state) => state.settings);

  useEffect(() => {
    fetchApi(`/strategies/${strategySlug}`, StrategySchema).then(setStrategy);
    fetchApi(`/strategies/${strategySlug}/backtest`, BacktestResponseSchema).then(setBacktest);
    fetchApi(`/strategies/${strategySlug}/backtest/equity-curve`, EquityCurveResponseSchema)
      .then(setEquityCurve)
      .catch(() => setEquityCurve(null));
  }, [strategySlug]);

  async function handleRun() {
    setLoading(true);
    try {
      const configuredEarningsWindow =
        settings.exclude_earnings_within_days_overrides[strategySlug] ??
        strategy?.default_exclude_earnings_within_days ??
        0;
      const effectiveEarningsWindow = earningsWindowOverride ?? configuredEarningsWindow;
      const effectiveExcludeEarnings = excludeEarningsOverride ?? configuredEarningsWindow > 0;
      const isSaudi = market === 'SA';
      const result = await fetchApi(`/strategies/${strategySlug}/run`, ScreenResultSchema, {
        method: 'POST',
        body: JSON.stringify({
          parameters: isSaudi
            ? { market: 'SA' } // backend injects the Saudi universe + SAR thresholds
            : {
                liquidity_min_avg_dollar_volume_20d: settings.liquidity_min_avg_dollar_volume_20d,
                liquidity_min_price: settings.liquidity_min_price,
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
        }),
      });
      setScreenResult(result);
      // Cache so navigating into a candidate detail and back doesn't re-run.
      setCachedScreen(strategySlug, { result, market, ranAt: Date.now() });
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

  if (!strategy || !backtest) {
    return <main className="mx-auto max-w-6xl px-6 py-8 text-sm text-slate-600">Loading strategy...</main>;
  }

  const configuredEarningsWindow =
    settings.exclude_earnings_within_days_overrides[strategySlug] ??
    strategy.default_exclude_earnings_within_days;
  const effectiveEarningsWindow = earningsWindowOverride ?? configuredEarningsWindow;
  const effectiveExcludeEarnings = excludeEarningsOverride ?? configuredEarningsWindow > 0;

  return (
    <main className="mx-auto max-w-6xl space-y-8 px-4 py-6 sm:px-6 lg:px-8">
      <header className="flex flex-col gap-4 border-b border-slate-200 pb-5 sm:flex-row sm:items-end sm:justify-between">
        <div className="space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-2xl font-semibold tracking-normal text-slate-950">{strategy.name}</h1>
            <span className="border border-slate-300 px-2 py-1 text-xs text-slate-700">{strategy.timeframe}</span>
          </div>
          <p className="max-w-3xl text-sm text-slate-600">{strategy.description}</p>
          <AsOfBadge date={backtest.data_as_of} sourceName={backtest.data_sources[0]?.source_name} />
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

      <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_minmax(360px,0.8fr)]">
        <StrategyGatesPanel strategy={strategy} />
        <WalkForwardMetricsPanel backtest={backtest} />
      </div>

      <EquityCurveCharts backtest={backtest} curve={equityCurve} />

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
            <AsOfBadge date={screenResult.data_as_of} />
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
          <div className="overflow-x-auto border border-slate-200 bg-white">
            <table className="data-table">
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
                  <th className="px-4 py-3">Events</th>
                  <th className="px-4 py-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody>
                {screenResult.candidates.map((candidate) => (
                  <CandidateRow candidate={candidate} key={candidate.ticker} strategySlug={strategySlug} timeframe={strategy.timeframe} />
                ))}
              </tbody>
            </table>
          </div>
          {screenResult.candidates.length === 0 ? (
            <div className="border border-slate-200 bg-white p-4 text-sm text-slate-600">No candidates matched the active filters.</div>
          ) : null}
        </section>
      ) : null}
    </main>
  );
}
