"use client";

import Link from 'next/link';
import { useAppStore } from '@/lib/store';

function money(value: string) {
  return `$${Number(value).toFixed(2)}`;
}

export default function WatchlistPage() {
  const watchlist = useAppStore((state) => state.watchlist);
  const updateWatchlistState = useAppStore((state) => state.updateWatchlistState);

  return (
    <main className="mx-auto max-w-5xl space-y-6 px-6 py-8">
      <header className="border-b border-gray-200 pb-5">
        <h1 className="text-2xl font-semibold text-gray-950">Watchlist</h1>
        <p className="text-sm text-gray-600">Saved candidates and their captured levels.</p>
      </header>

      {watchlist.length === 0 ? (
        <div className="border border-gray-200 p-6 text-sm text-gray-600">No saved candidates yet.</div>
      ) : (
        <div className="overflow-x-auto border border-gray-200">
          <table className="min-w-full text-left text-sm">
            <thead className="bg-gray-50 text-xs uppercase text-gray-500">
              <tr>
                <th className="px-4 py-3">Ticker</th>
                <th className="px-4 py-3">Sector</th>
                <th className="px-4 py-3">State</th>
                <th className="px-4 py-3 text-right">Entry</th>
                <th className="px-4 py-3 text-right">Stop</th>
                <th className="px-4 py-3 text-right">Target</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {watchlist.map((entry) => (
                <tr className="border-t border-gray-200" key={entry.id}>
                  <td className="px-4 py-3">
                    <Link
                      className="font-semibold text-gray-950 underline-offset-2 hover:underline"
                      href={`/analyze?ticker=${encodeURIComponent(entry.ticker)}`}
                      title={`Analyze ${entry.ticker}`}
                    >
                      {entry.ticker}
                    </Link>
                    <div className="text-xs text-gray-500">{entry.name}</div>
                  </td>
                  <td className="px-4 py-3 text-gray-700">{entry.sector}</td>
                  <td className="px-4 py-3 capitalize text-gray-700">{entry.state.replace('_', ' ')}</td>
                  <td className="px-4 py-3 text-right">{money(entry.levels_snapshot.entry)}</td>
                  <td className="px-4 py-3 text-right">{money(entry.levels_snapshot.stop_loss)}</td>
                  <td className="px-4 py-3 text-right">{money(entry.levels_snapshot.take_profit)}</td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex justify-end gap-2">
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
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </main>
  );
}
