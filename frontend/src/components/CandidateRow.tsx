"use client";

import { useState } from 'react';
import Link from 'next/link';
import { Candidate, postSizing } from '@/lib/api';
import { formatMoney } from '@/lib/format';
import { useAppStore } from '@/lib/store';
import { EventsBadge } from './EventsBadge';
import { ShariahBadge } from './ShariahBadge';

function stopDistance(entry: string, stop: string) {
  const entryValue = Number(entry);
  const stopValue = Number(stop);
  if (!Number.isFinite(entryValue) || !Number.isFinite(stopValue) || entryValue <= 0) {
    return null;
  }
  return `${(((entryValue - stopValue) / entryValue) * 100).toFixed(1)}%`;
}

export function CandidateRow({
  candidate,
  strategySlug,
  timeframe,
  sectorTopFraction,
}: {
  candidate: Candidate;
  strategySlug: string;
  timeframe?: string;
  sectorTopFraction?: number;
}) {
  const saveCandidate = useAppStore((state) => state.saveCandidate);
  const addHolding = useAppStore((state) => state.addHolding);
  const portfolio = useAppStore((state) => state.portfolio);
  const settings = useAppStore((state) => state.settings);
  const [adding, setAdding] = useState(false);
  const rowTimeframe = timeframe || candidate.timeframe;
  const distance = stopDistance(candidate.entry, candidate.stop_loss);
  // Carry the screen's strategy + sector-gate toggle into the detail page so its
  // gate breakdown matches what was screened (not a default re-run).
  const detailQuery = new URLSearchParams({ strategy: strategySlug });
  if (sectorTopFraction !== undefined) {
    detailQuery.set('sector', String(sectorTopFraction));
  }
  const detailHref = `/candidate/${candidate.ticker}?${detailQuery.toString()}`;

  async function addToPortfolio() {
    setAdding(true);
    try {
      const sizing = await postSizing({
        candidate_ticker: candidate.ticker,
        entry: candidate.entry,
        candidate_sector: candidate.sector,
        total_capital: String(portfolio.total_capital),
        holdings: portfolio.holdings.map((holding) => ({
          ticker: holding.ticker,
          shares: String(holding.shares),
          current_price: String(holding.current_price),
          sector: holding.sector,
        })),
        caps: {
          per_position_cap_pct: settings.per_position_cap_pct,
          per_sector_cap_pct: settings.per_sector_cap_pct,
        },
      });
      const suggested = sizing.result.caps_respected ? sizing.result.suggested_shares : 0;
      const fallback = suggested > 0 ? String(suggested) : '1';
      const rawShares = window.prompt(`Shares for ${candidate.ticker}`, fallback);
      const shares = Number(rawShares);
      if (!Number.isFinite(shares) || shares <= 0) {
        return;
      }
      addHolding({
        ticker: candidate.ticker,
        shares,
        avg_cost: Number(candidate.entry),
        current_price: Number(candidate.current_price),
        sector: candidate.sector,
      });
    } finally {
      setAdding(false);
    }
  }

  return (
    <tr className="border-b border-slate-200 last:border-b-0 hover:bg-slate-50">
      <td className="px-4 py-3">
        <Link className="font-semibold text-slate-950 underline-offset-2 hover:underline" href={detailHref}>
          {candidate.ticker}
        </Link>
        <div className="text-xs text-slate-500">{candidate.name}</div>
        {candidate.return_12_1 !== undefined && candidate.return_12_1 !== null ? (
          <div
            className={`mt-1 text-xs font-bold ${
              candidate.return_12_1 >= 0 ? 'text-emerald-700' : 'text-red-700'
            }`}
          >
            12-1 Mom: {candidate.return_12_1 >= 0 ? '+' : ''}
            {(candidate.return_12_1 * 100).toFixed(1)}%
          </div>
        ) : null}
        {rowTimeframe ? <div className="mt-1 text-xs font-medium text-slate-700">{rowTimeframe}</div> : null}
        {candidate.data_suspect ? (
          <div
            className="mt-1 inline-flex items-center gap-1 bg-red-100 px-1.5 py-0.5 text-xs font-bold text-red-800"
            title={candidate.data_integrity_warnings.map((w) => w.reason).join('\n')}
          >
            🛑 DATA INTEGRITY
          </div>
        ) : null}
        {candidate.warnings && candidate.warnings.length > 0 ? (
          <div
            className="mt-1 inline-flex items-center gap-1 bg-amber-100 px-1.5 py-0.5 text-xs font-medium text-amber-800"
            title={candidate.warnings.join('\n')}
          >
            ⚠ {candidate.warnings.length} soft-gate {candidate.warnings.length === 1 ? 'warning' : 'warnings'}
          </div>
        ) : null}
      </td>
      <td className="px-4 py-3 text-sm text-slate-700">{candidate.sector}</td>
      <td className="px-4 py-3 text-sm text-slate-700">
        {candidate.shariah_compliant !== null && candidate.shariah_compliant !== undefined ? (
          <ShariahBadge status={candidate} />
        ) : (
          <span className="text-xs text-slate-400">-</span>
        )}
      </td>
      <td className="px-4 py-3 text-right text-sm text-slate-700">{formatMoney(candidate.current_price, candidate.ticker)}</td>
      <td className="px-4 py-3 text-right text-sm font-medium text-slate-950">{formatMoney(candidate.entry, candidate.ticker)}</td>
      <td className="px-4 py-3 text-right text-sm text-slate-700">
        <div>{formatMoney(candidate.stop_loss, candidate.ticker)}</div>
        {distance ? <div className="text-xs text-slate-500">{distance} risk</div> : null}
        {candidate.tighter_stop_loss &&
        Number(candidate.tighter_stop_loss) > Number(candidate.stop_loss) ? (
          <div className="mt-1 text-xs text-emerald-700">
            tighter: {formatMoney(candidate.tighter_stop_loss, candidate.ticker)}
            {(() => {
              const d = stopDistance(candidate.entry, candidate.tighter_stop_loss);
              return d ? ` (${d} risk)` : '';
            })()}
          </div>
        ) : null}
      </td>
      <td className="px-4 py-3 text-right text-sm text-slate-700">{formatMoney(candidate.take_profit, candidate.ticker)}</td>
      <td className="px-4 py-3 text-sm text-slate-700">{candidate.reason}</td>
      <td className="px-4 py-3 text-sm text-slate-700">
        <EventsBadge candidate={candidate} />
      </td>
      <td className="space-y-2 px-4 py-3 text-right">
        <button
          type="button"
          className="w-full border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-800 hover:bg-slate-100"
          onClick={() =>
            saveCandidate({
              ticker: candidate.ticker,
              name: candidate.name,
              sector: candidate.sector,
              strategy_slug: strategySlug,
              levels_snapshot: {
                entry: candidate.entry,
                stop_loss: candidate.stop_loss,
                take_profit: candidate.take_profit,
              },
            })
          }
        >
          Save
        </button>
        <button
          type="button"
          className="w-full border border-slate-950 bg-slate-950 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
          disabled={adding}
          onClick={addToPortfolio}
        >
          {adding ? 'Adding...' : 'Add to portfolio'}
        </button>
      </td>
    </tr>
  );
}
