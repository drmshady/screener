"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import { EntryStatus, EntryTiming, fetchEntryStatus } from '@/lib/api';
import { useAppStore, WatchlistEntry } from '@/lib/store';
import { CopyWatchlistAdvisorPrompt } from '@/components/CopyWatchlistAdvisorPrompt';

function money(value: string) {
  return `$${Number(value).toFixed(2)}`;
}

type LiveState = 'entry_ready' | 'not_entry_ready' | 'entry_undetermined';

interface RowStatus {
  liveState: LiveState;
  summary: string;
  failingReasons: string[];
  dataAsOf: string | null;
  newlyReady: boolean;
}

const UNDETERMINED: RowStatus = {
  liveState: 'entry_undetermined',
  summary: 'Live entry-timing is not available for this ticker.',
  failingReasons: [],
  dataAsOf: null,
  newlyReady: false,
};

// Module-level promise cache so repeated renders reuse one in-flight/settled
// request per ticker (dedupe) and the same snapshot yields the same read-out
// (determinism). A manual refresh clears it to force a re-check.
const entryStatusCache = new Map<string, Promise<EntryStatus>>();

function cacheKey(ticker: string, strategySlug: string) {
  return `${ticker}::${strategySlug}`;
}

function loadEntryStatus(ticker: string, strategySlug: string): Promise<EntryStatus> {
  const key = cacheKey(ticker, strategySlug);
  const cached = entryStatusCache.get(key);
  if (cached) {
    return cached;
  }
  const promise = fetchEntryStatus(ticker, strategySlug);
  entryStatusCache.set(key, promise);
  return promise;
}

function topFailingReasons(timing: EntryTiming): string[] {
  const reasons = timing.components
    .filter((component) => component.status === 'fail')
    .map((component) => component.reason);
  const disqualifiers = (timing.disqualifiers ?? [])
    .filter((d) => d.triggered)
    .map((d) => d.reason);
  return [...reasons, ...disqualifiers].slice(0, 3);
}

function toRowStatus(status: EntryStatus, baseline: LiveState | undefined): RowStatus {
  const timing = status.entry_timing;
  if (!timing) {
    return { ...UNDETERMINED, dataAsOf: status.data_as_of };
  }
  return {
    liveState: timing.state,
    summary: timing.summary,
    failingReasons: timing.state === 'not_entry_ready' ? topFailingReasons(timing) : [],
    dataAsOf: status.data_as_of,
    newlyReady: timing.state === 'entry_ready' && baseline !== undefined && baseline !== 'entry_ready',
  };
}

const STATE_RANK: Record<LiveState, number> = {
  entry_ready: 0,
  not_entry_ready: 1,
  entry_undetermined: 2,
};

function stateLabel(liveState: LiveState): string {
  if (liveState === 'entry_ready') return 'Entry ready';
  if (liveState === 'not_entry_ready') return 'Watching — not yet ready';
  return 'Undetermined';
}

function badgeClasses(liveState: LiveState): string {
  if (liveState === 'entry_ready') {
    return 'border-emerald-300 bg-emerald-50 text-emerald-900';
  }
  if (liveState === 'not_entry_ready') {
    return 'border-amber-300 bg-amber-50 text-amber-900';
  }
  return 'border-gray-300 bg-gray-50 text-gray-600';
}

export default function WatchlistPage() {
  const watchlist = useAppStore((state) => state.watchlist);
  const updateWatchlistState = useAppStore((state) => state.updateWatchlistState);
  const setWatchlistEntryStatus = useAppStore((state) => state.setWatchlistEntryStatus);

  const [statuses, setStatuses] = useState<Record<string, RowStatus>>({});
  const [refreshNonce, setRefreshNonce] = useState(0);

  // Open = not yet acted on / dismissed. Only these are actively re-checked.
  const openEntries = useMemo(
    () => watchlist.filter((entry) => entry.state === 'saved'),
    [watchlist],
  );

  // Feature 017 (US3): the watched tickers + the strategy to export them under.
  // When every open entry shares one strategy we honor it; a mixed watchlist
  // falls back to the primary momentum strategy.
  const exportTickers = useMemo(() => openEntries.map((entry) => entry.ticker), [openEntries]);
  const exportStrategy = useMemo(() => {
    const slugs = new Set(openEntries.map((entry) => entry.strategy_slug));
    return slugs.size === 1 ? openEntries[0].strategy_slug : 'midterm_52w_high_momentum';
  }, [openEntries]);

  // Baseline of the last persisted live state per entry, captured once (inside
  // the fetch effect, before we overwrite it), so we can flag a ticker that
  // newly became entry-ready since the owner last looked.
  const baselineRef = useRef<Record<string, LiveState | undefined>>({});

  const openIdsKey = openEntries.map((entry) => `${entry.id}:${entry.ticker}`).join(',');

  useEffect(() => {
    let cancelled = false;
    for (const entry of openEntries) {
      if (!(entry.id in baselineRef.current)) {
        baselineRef.current[entry.id] = entry.last_entry_state;
      }
      const baseline = baselineRef.current[entry.id];
      loadEntryStatus(entry.ticker, entry.strategy_slug)
        .then((status) => {
          if (cancelled) return;
          const row = toRowStatus(status, baseline);
          setStatuses((prev) => ({ ...prev, [entry.id]: row }));
          if (row.dataAsOf) {
            setWatchlistEntryStatus(entry.id, row.liveState, row.dataAsOf);
          }
        })
        .catch(() => {
          if (cancelled) return;
          setStatuses((prev) => ({ ...prev, [entry.id]: { ...UNDETERMINED } }));
        });
    }
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [openIdsKey, refreshNonce]);

  const refresh = useCallback(() => {
    entryStatusCache.clear();
    setRefreshNonce((nonce) => nonce + 1);
  }, []);

  const sortedEntries = useMemo(() => {
    const rankOf = (entry: WatchlistEntry) =>
      STATE_RANK[statuses[entry.id]?.liveState ?? 'entry_undetermined'];
    return [...openEntries]
      .map((entry, index) => ({ entry, index }))
      .sort((a, b) => rankOf(a.entry) - rankOf(b.entry) || a.index - b.index)
      .map((item) => item.entry);
  }, [openEntries, statuses]);

  return (
    <main className="mx-auto max-w-5xl space-y-6 px-6 py-8">
      <header className="flex items-start justify-between border-b border-gray-200 pb-5">
        <div>
          <h1 className="text-2xl font-semibold text-gray-950">Watchlist</h1>
          <p className="text-sm text-gray-600">
            Saved candidates, re-checked for live entry-timing so you can watch a name until it
            becomes entry-ready. Informational status only.
          </p>
        </div>
        {openEntries.length > 0 ? (
          <div className="flex shrink-0 items-start gap-2">
            <CopyWatchlistAdvisorPrompt tickers={exportTickers} strategySlug={exportStrategy} />
            <button
              className="shrink-0 border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-800 hover:bg-gray-100"
              onClick={refresh}
              type="button"
            >
              Refresh
            </button>
          </div>
        ) : null}
      </header>

      {openEntries.length === 0 ? (
        <div className="border border-gray-200 p-6 text-sm text-gray-600">
          No active saved candidates. Add a candidate from a screen result to watch it until it
          becomes entry-ready.
        </div>
      ) : (
        <ul className="space-y-3">
          {sortedEntries.map((entry) => {
            const status = statuses[entry.id];
            const loading = status === undefined;
            const row = status ?? UNDETERMINED;
            const newlyReady = row.newlyReady;
            return (
              <li
                className={`border p-4 ${
                  !loading && row.liveState === 'entry_ready'
                    ? 'border-emerald-300 bg-emerald-50/40'
                    : 'border-gray-200'
                }`}
                key={entry.id}
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <Link
                        className="font-semibold text-gray-950 underline-offset-2 hover:underline"
                        data-testid="watchlist-ticker"
                        href={`/analyze?ticker=${encodeURIComponent(entry.ticker)}`}
                        title={`Analyze ${entry.ticker}`}
                      >
                        {entry.ticker}
                      </Link>
                      <span className="text-xs text-gray-500">{entry.name}</span>
                      {newlyReady ? (
                        <span className="border border-emerald-400 bg-emerald-100 px-1.5 py-0.5 text-xs font-semibold text-emerald-900">
                          Newly ready
                        </span>
                      ) : null}
                    </div>
                    <div className="text-xs text-gray-500">{entry.sector}</div>
                  </div>

                  <div className="min-w-56 space-y-1 text-right">
                    <span
                      className={`inline-block border px-2 py-0.5 text-xs font-semibold ${badgeClasses(
                        row.liveState,
                      )}`}
                    >
                      {loading ? 'Checking…' : stateLabel(row.liveState)}
                    </span>
                    {row.summary && !loading ? (
                      <div className="text-xs text-gray-600">{row.summary}</div>
                    ) : null}
                    {!loading && row.dataAsOf ? (
                      <div className="text-xs text-gray-400">Last checked {row.dataAsOf}</div>
                    ) : null}
                  </div>
                </div>

                {!loading && row.failingReasons.length > 0 ? (
                  <ul className="mt-3 list-disc space-y-0.5 pl-5 text-xs text-amber-800">
                    {row.failingReasons.map((reason) => (
                      <li key={reason}>{reason}</li>
                    ))}
                  </ul>
                ) : null}

                <div className="mt-3 flex flex-wrap items-center justify-between gap-3 border-t border-gray-100 pt-3">
                  <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-gray-500">
                    <span>Captured entry {money(entry.levels_snapshot.entry)}</span>
                    <span>stop {money(entry.levels_snapshot.stop_loss)}</span>
                    <span>target {money(entry.levels_snapshot.take_profit)}</span>
                  </div>
                  <div className="flex gap-2">
                    <button
                      className="border border-gray-300 px-2 py-1 text-xs hover:bg-gray-100"
                      onClick={() => updateWatchlistState(entry.id, 'acted_on')}
                      type="button"
                    >
                      Mark acted on
                    </button>
                    <button
                      className="border border-gray-300 px-2 py-1 text-xs hover:bg-gray-100"
                      onClick={() => updateWatchlistState(entry.id, 'dismissed')}
                      type="button"
                    >
                      Dismiss
                    </button>
                  </div>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </main>
  );
}
