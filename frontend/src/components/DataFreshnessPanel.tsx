"use client";

import { useEffect, useState } from 'react';
import {
  DataFreshnessResponse,
  DataRefreshResponse,
  getDataFreshness,
  hostedModeEnabled,
  refreshData,
} from '@/lib/api';
import { STATUS_TONES } from '@/lib/design';

function sourceLabel(sourceName: string) {
  if (sourceName === 'yfinance') {
    return 'yfinance';
  }
  if (sourceName === 'stooq') {
    return 'Stooq';
  }
  return sourceName;
}

export function DataFreshnessPanel() {
  const [freshness, setFreshness] = useState<DataFreshnessResponse | null>(null);
  const [refreshResult, setRefreshResult] = useState<DataRefreshResponse | null>(null);
  const [error, setError] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const hosted = hostedModeEnabled();

  useEffect(() => {
    getDataFreshness()
      .then((payload) => {
        setFreshness(payload);
        setError(false);
      })
      .catch(() => setError(true));
  }, []);

  async function handleRefresh() {
    setRefreshing(true);
    try {
      const result = await refreshData('US');
      setRefreshResult(result);
      setFreshness(await getDataFreshness());
      setError(false);
    } catch {
      setError(true);
    } finally {
      setRefreshing(false);
    }
  }

  if (error) {
    return (
      <section className={`${STATUS_TONES.warning} border p-4 text-sm`}>
        Data freshness is unavailable.
      </section>
    );
  }

  const priceSources =
    freshness?.sources.filter((source) => source.kind === 'prices') ?? [];
  const primaryPriceSource =
    priceSources.find((source) => source.source_name === 'yfinance') ??
    priceSources[0];

  if (!primaryPriceSource) {
    return (
      <section className="panel p-4 text-sm text-slate-600">
        Loading data freshness...
      </section>
    );
  }

  const asOf = primaryPriceSource.data_as_of ?? 'unknown';
  const staleSources = freshness?.sources.filter((source) => source.is_stale) ?? [];

  return (
    <section className="panel flex flex-col gap-3 p-4 text-sm text-slate-700 sm:flex-row sm:items-center sm:justify-between">
      <div className="space-y-1">
        <div className="font-medium text-slate-950">Prices as of {asOf}</div>
        <div className="text-slate-600">
          Source: {sourceLabel(primaryPriceSource.source_name)}
        </div>
        <div className="text-slate-600">
          Latest completed session: {freshness?.latest_session ?? 'unknown'}
        </div>
        {staleSources.length > 0 ? (
          <div>
            Stale sources:{' '}
            {staleSources
              .map((source) => `${sourceLabel(source.source_name)} (${source.data_as_of ?? 'unknown'})`)
              .join(', ')}
          </div>
        ) : null}
        {hosted ? (
          <div>
            Refresh the local snapshot and republish the backend image; this hosted instance
            serves cached data only.
          </div>
        ) : null}
        {refreshResult?.latest_bar ? (
          <div>Latest refreshed price bar: {refreshResult.latest_bar}</div>
        ) : null}
        {refreshResult?.notices.map((notice) => (
          <div key={notice}>{notice}</div>
        ))}
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <span
          className={`w-fit border px-2 py-1 text-xs font-medium ${
            primaryPriceSource.is_stale
              ? STATUS_TONES.warning
              : STATUS_TONES.success
          }`}
        >
          {primaryPriceSource.is_stale ? 'Stale' : 'Fresh'}
        </span>
        {!hosted ? (
          <button
            className="border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-800 hover:bg-slate-100 disabled:opacity-60"
            disabled={refreshing}
            onClick={handleRefresh}
            type="button"
          >
            {refreshing ? 'Refreshing...' : 'Refresh'}
          </button>
        ) : null}
      </div>
    </section>
  );
}
