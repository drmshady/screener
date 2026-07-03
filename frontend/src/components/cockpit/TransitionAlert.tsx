"use client";

import { STATUS_TONES } from '@/lib/design';

/** One entry-ready candidate the owner is watching, with how long it has been
 *  ready and whether the owner has acknowledged the transition. */
export interface ReadyAlert {
  ticker: string;
  /** Whole days since the candidate first became entry-ready (0 = today). */
  days: number;
  /** True once the owner has dismissed the "newly ready" flag for this ticker. */
  acknowledged: boolean;
}

function readyForLabel(days: number): string {
  if (days <= 0) return 'ready today';
  if (days === 1) return 'ready for 1 day';
  return `ready for ${days} days`;
}

/**
 * Surfaces momentum candidates that have become entry-ready since the owner
 * last looked ("newly ready") plus a plain "ready for N days" counter for the
 * rest. Neutral, descriptive only — it reports a state change, never an action.
 * Renders nothing when no watched candidate is currently ready.
 */
export function TransitionAlert({
  alerts,
  onAcknowledge,
}: {
  alerts: ReadyAlert[];
  onAcknowledge: (ticker: string) => void;
}) {
  if (alerts.length === 0) {
    return null;
  }
  const newlyReady = alerts.filter((alert) => !alert.acknowledged);
  const standing = alerts.filter((alert) => alert.acknowledged);

  return (
    <section className="panel space-y-3 p-5" data-testid="transition-alerts">
      <div className="flex items-baseline justify-between">
        <h2 className="text-lg font-semibold text-slate-950">Readiness</h2>
        <span className="text-xs text-slate-500">Entry-timing changes on your watchlist</span>
      </div>

      {newlyReady.length > 0 ? (
        <ul className="space-y-2">
          {newlyReady.map((alert) => (
            <li
              key={alert.ticker}
              className={`${STATUS_TONES.success} flex flex-wrap items-center justify-between gap-2 border p-3 text-sm`}
              data-testid="newly-ready-alert"
            >
              <span className="flex items-center gap-2">
                <span className="inline-flex border border-emerald-400 bg-white px-2 py-0.5 text-xs font-semibold text-emerald-800">
                  Newly ready
                </span>
                <span className="font-semibold text-slate-950">{alert.ticker}</span>
                <span className="text-slate-600">{readyForLabel(alert.days)}</span>
              </span>
              <button
                type="button"
                className="border border-emerald-400 bg-white px-2 py-1 text-xs font-medium text-emerald-800 hover:bg-emerald-50"
                onClick={() => onAcknowledge(alert.ticker)}
                data-testid="acknowledge-ready"
              >
                Acknowledge
              </button>
            </li>
          ))}
        </ul>
      ) : null}

      {standing.length > 0 ? (
        <ul className="flex flex-wrap gap-2">
          {standing.map((alert) => (
            <li
              key={alert.ticker}
              className="inline-flex items-center gap-1 border border-slate-200 bg-slate-50 px-2 py-1 text-xs text-slate-600"
              data-testid="standing-ready"
            >
              <span className="font-semibold text-slate-800">{alert.ticker}</span>
              <span>{readyForLabel(alert.days)}</span>
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}
