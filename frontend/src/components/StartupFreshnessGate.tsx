"use client";

import { useEffect, useMemo, useState } from 'react';
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
  if (sourceName === 'sec_edgar_company_tickers') {
    return 'SEC company tickers';
  }
  if (sourceName === 'ticker_profile_cache') {
    return 'Fundamentals cache';
  }
  return sourceName.replaceAll('_', ' ');
}

// No source carries a date when the read-only snapshot is absent (e.g. a fresh
// instance before the first publish, or a missing/partial snapshot). Surface
// this as an explicit maintenance state rather than an error or blank page.
function snapshotMissing(freshness: DataFreshnessResponse) {
  return (
    freshness.sources.length > 0 &&
    freshness.sources.every((source) => source.data_as_of === null)
  );
}

function staleSourceText(freshness: DataFreshnessResponse) {
  const stale = freshness.sources.filter((source) => source.is_stale);
  if (stale.length === 0) {
    return 'Data is current';
  }
  return stale
    .map((source) => {
      const asOf = source.data_as_of ?? 'unknown';
      return `${sourceLabel(source.source_name)} as of ${asOf}`;
    })
    .join(', ');
}

export function StartupFreshnessGate() {
  const [freshness, setFreshness] = useState<DataFreshnessResponse | null>(null);
  const [dismissed, setDismissed] = useState(false);
  const [failed, setFailed] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [refreshFailed, setRefreshFailed] = useState(false);
  const [refreshResult, setRefreshResult] = useState<DataRefreshResponse | null>(null);
  const hosted = hostedModeEnabled();

  useEffect(() => {
    let active = true;
    getDataFreshness()
      .then((payload) => {
        if (!active) {
          return;
        }
        setFreshness(payload);
        setFailed(false);
      })
      .catch(() => {
        if (active) {
          setFailed(true);
        }
      });
    return () => {
      active = false;
    };
  }, []);

  const sourceText = useMemo(
    () => (freshness ? staleSourceText(freshness) : ''),
    [freshness],
  );

  if (failed) {
    return (
      <div className={`${STATUS_TONES.warning} border px-4 py-2 text-sm`} role="status">
        Data freshness check unavailable. Cached data remains usable.
      </div>
    );
  }

  if (!freshness) {
    return null;
  }

  if (snapshotMissing(freshness)) {
    return (
      <div className={`${STATUS_TONES.warning} border px-4 py-3 text-sm`} role="status">
        <div className="font-medium">Data snapshot unavailable</div>
        <div>
          The screener is in maintenance: no published data snapshot is available yet.
          {hosted
            ? ' Refresh data locally and republish the backend image to bring it online.'
            : ' Seed or refresh the local data before running a screen.'}
        </div>
      </div>
    );
  }

  if (dismissed && freshness.any_stale) {
    return (
      <div className={`${STATUS_TONES.info} border px-4 py-2 text-sm`} role="status">
        Proceeding on cached data. {sourceText}
      </div>
    );
  }

  if (!freshness.any_stale) {
    return (
      <div className={`${STATUS_TONES.success} border px-4 py-2 text-sm`} role="status">
        Data is current for latest completed session {freshness.latest_session}.
      </div>
    );
  }

  async function handleRefresh() {
    setRefreshing(true);
    try {
      const result = await refreshData('US');
      setRefreshResult(result);
      setRefreshFailed(false);
      const nextFreshness = await getDataFreshness();
      setFreshness(nextFreshness);
      if (!nextFreshness.any_stale) {
        setDismissed(true);
      }
    } catch {
      setRefreshFailed(true);
    } finally {
      setRefreshing(false);
    }
  }

  return (
    <div className={`${STATUS_TONES.warning} border px-4 py-3 text-sm`} role="status">
      <div className="mx-auto flex max-w-7xl flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="font-medium">Cached data needs attention</div>
          <div>{sourceText}</div>
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
          {refreshFailed ? <div>Refresh failed; cached data remains usable.</div> : null}
        </div>
        <div className="flex flex-wrap gap-2">
          {!hosted ? (
            <button
              className="border border-amber-700 bg-white px-3 py-2 text-sm font-medium text-amber-950 hover:bg-amber-100 disabled:opacity-60"
              disabled={refreshing}
              onClick={handleRefresh}
              type="button"
            >
              {refreshing ? 'Refreshing...' : 'Refresh now'}
            </button>
          ) : null}
          <button
            className="border border-amber-400 px-3 py-2 text-sm font-medium text-amber-950 hover:bg-amber-100"
            onClick={() => setDismissed(true)}
            type="button"
          >
            Proceed on cached data
          </button>
        </div>
      </div>
    </div>
  );
}
