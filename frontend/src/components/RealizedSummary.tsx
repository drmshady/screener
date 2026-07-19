"use client";

import { AsOfBadge } from '@/components/AsOfBadge';
import { formatMoney } from '@/lib/format';

/**
 * Just the realized fields this scoreboard reads. Kept structurally loose (all
 * optional) so both the full `PortfolioTotals` and the Portfolio page's inline
 * totals shape are assignable without coupling.
 */
export interface RealizedTotalsLike {
  realized_pnl?: string | null;
  win_rate?: number | null;
  closed_trade_count?: number;
  winning_trade_count?: number;
}

/**
 * Realized win/loss scoreboard (Feature 019, US4): count won, count lost, win
 * rate %, and total realized P&L across fully-closed positions. It reads the
 * existing `PortfolioTotals` realized fields directly — no new computation
 * (data-model.md) — and shows an explicit "No realized history yet" empty state
 * when nothing has closed (FR-009). Carries `data_as_of` + the disclaimer
 * (FR-012). Presentation only: no directive language.
 */

export interface RealizedSummaryProps {
  totals: RealizedTotalsLike | null;
  /** Response-level as-of for the footer (FR-012). */
  dataAsOf?: string | null;
  disclaimer: string;
}

export function RealizedSummary({ totals, dataAsOf = null, disclaimer }: RealizedSummaryProps) {
  const closed = totals?.closed_trade_count ?? 0;
  const won = totals?.winning_trade_count ?? 0;
  const lost = Math.max(closed - won, 0);
  const winRate = totals?.win_rate ?? null;
  const realized = totals?.realized_pnl ?? null;
  const realizedGain = realized != null ? Number(realized) >= 0 : true;

  return (
    <section
      aria-label="Realized win/loss summary"
      className="space-y-3 border border-slate-200 bg-white p-5 shadow-sm"
      data-testid="realized-summary"
    >
      <h2 className="text-lg font-semibold text-slate-950">Realized win/loss</h2>

      {closed > 0 ? (
        <dl className="grid grid-cols-2 gap-x-4 gap-y-3 text-sm sm:grid-cols-4">
          <div>
            <dt className="text-xs uppercase text-slate-500">Won</dt>
            <dd className="text-xl font-semibold text-emerald-700" data-testid="realized-won">
              {won}
            </dd>
          </div>
          <div>
            <dt className="text-xs uppercase text-slate-500">Lost</dt>
            <dd className="text-xl font-semibold text-rose-700" data-testid="realized-lost">
              {lost}
            </dd>
          </div>
          <div>
            <dt className="text-xs uppercase text-slate-500">Win rate</dt>
            <dd className="text-xl font-semibold text-slate-900" data-testid="realized-win-rate">
              {winRate != null ? `${(winRate * 100).toFixed(0)}%` : '—'}
            </dd>
          </div>
          <div>
            <dt className="text-xs uppercase text-slate-500">Total realized P/L</dt>
            <dd
              className={`text-xl font-semibold ${realizedGain ? 'text-emerald-700' : 'text-rose-700'}`}
              data-testid="realized-total"
            >
              {realized != null ? formatMoney(realized) : '—'}
            </dd>
          </div>
        </dl>
      ) : (
        <p className="text-sm text-slate-500" data-testid="realized-empty">
          No realized history yet — close a position to build your win/loss record.
        </p>
      )}

      <footer className="mt-1 flex flex-wrap items-center gap-2 border-t border-slate-100 pt-3 text-xs text-slate-500">
        {dataAsOf ? <AsOfBadge date={dataAsOf} /> : null}
        <span data-testid="realized-disclaimer">{disclaimer}</span>
      </footer>
    </section>
  );
}
