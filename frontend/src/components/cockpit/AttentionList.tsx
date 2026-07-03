"use client";

import Link from 'next/link';
import { STATUS_TONES } from '@/lib/design';
import { PipelineStageBadge } from './PipelineStageBadge';

export interface AttentionRow {
  ticker: string;
  /** Neutral, descriptive reason this holding surfaced (e.g. a level status). */
  message: string;
  severity: 'high' | 'medium';
}

/**
 * Open holdings that have moved past a calm state — a level breached/reached, a
 * protected trailing stop, or an over-budget position. Descriptive only
 * (no directive language, FR-020); each row links back into the portfolio for
 * the full level/risk detail. Empty state is an onboarding prompt (FR-014).
 */
export function AttentionList({ rows }: { rows: AttentionRow[] }) {
  if (rows.length === 0) {
    return (
      <section className="panel space-y-2 p-5" data-testid="attention-list">
        <h2 className="text-lg font-semibold text-slate-950">Holdings needing attention</h2>
        <p className="text-sm text-slate-600">
          No open holding has reached a stop, target, or risk limit. Imported and manual holdings
          appear here when a level changes.
        </p>
      </section>
    );
  }

  return (
    <section className="panel space-y-3 p-5" data-testid="attention-list">
      <div className="flex items-baseline justify-between">
        <h2 className="text-lg font-semibold text-slate-950">Holdings needing attention</h2>
        <span className="text-xs text-slate-500">{rows.length} flagged</span>
      </div>
      <ul className="space-y-2">
        {rows.map((row) => (
          <li
            key={row.ticker}
            className={`${
              row.severity === 'high' ? STATUS_TONES.danger : STATUS_TONES.warning
            } flex flex-wrap items-center justify-between gap-2 border p-3 text-sm`}
            data-testid="attention-row"
          >
            <span className="flex items-center gap-2">
              <span className="font-semibold text-slate-950">{row.ticker}</span>
              <PipelineStageBadge stage="managing" />
              <span>{row.message}</span>
            </span>
            <Link
              className="border border-slate-300 bg-white px-2 py-1 text-xs font-medium text-slate-800 hover:bg-slate-100"
              href="/portfolio"
            >
              Review
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
