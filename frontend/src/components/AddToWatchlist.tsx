"use client";

import { useMemo, useState } from 'react';
import { Candidate } from '@/lib/api';
import { useAppStore } from '@/lib/store';

type WatchlistStatus = 'added' | 'duplicate' | null;

export function AddToWatchlist({
  candidate,
  strategySlug,
  className = '',
  buttonClassName = '',
}: {
  candidate: Candidate;
  strategySlug: string;
  className?: string;
  buttonClassName?: string;
}) {
  const saveCandidate = useAppStore((state) => state.saveCandidate);
  const watchlist = useAppStore((state) => state.watchlist);
  const [status, setStatus] = useState<WatchlistStatus>(null);
  const symbol = candidate.ticker.toUpperCase();
  const existing = useMemo(
    () =>
      watchlist.find(
        (entry) => entry.ticker.toUpperCase() === symbol && entry.strategy_slug === strategySlug,
      ),
    [strategySlug, symbol, watchlist],
  );

  function addToWatchlist() {
    if (existing) {
      setStatus('duplicate');
      return;
    }
    saveCandidate({
      ticker: symbol,
      name: candidate.name,
      sector: candidate.sector,
      strategy_slug: strategySlug,
      levels_snapshot: {
        entry: candidate.entry,
        stop_loss: candidate.stop_loss,
        take_profit: candidate.take_profit,
      },
    });
    setStatus('added');
  }

  const isWatched = Boolean(existing);
  const message =
    status === 'added'
      ? 'Added to watchlist'
      : status === 'duplicate'
        ? 'Already watched'
        : null;

  return (
    <div className={className}>
      <button
        type="button"
        className={buttonClassName}
        onClick={addToWatchlist}
        title="Watch this candidate until it becomes entry-ready"
      >
        {isWatched ? 'Already watched' : 'Add to watchlist'}
      </button>
      {message ? (
        <div aria-live="polite" className="mt-1 text-xs font-medium text-emerald-700">
          {message}
        </div>
      ) : null}
    </div>
  );
}
