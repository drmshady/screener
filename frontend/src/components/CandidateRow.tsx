"use client";

import { useState } from 'react';
import Link from 'next/link';
import { Candidate, postSizing } from '@/lib/api';
import { formatMoney } from '@/lib/format';
import { useAppStore } from '@/lib/store';
import { AddToWatchlist } from './AddToWatchlist';
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

function entryStateLabel(state: NonNullable<Candidate['entry_timing']>['state']) {
  if (state === 'entry_ready') return 'Entry-ready';
  if (state === 'not_entry_ready') return 'Not entry-ready';
  return 'Entry undetermined';
}

function componentLabel(name: string) {
  return name.replaceAll('_', ' ');
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
        {candidate.skipped_gates && candidate.skipped_gates.length > 0 ? (
          <div
            className="mt-1 inline-flex items-center gap-1 border border-slate-300 bg-slate-100 px-1.5 py-0.5 text-xs font-medium text-slate-700"
            title={candidate.skipped_gates.map((s) => `${s.gate}: ${s.reason}`).join('\n')}
          >
            {candidate.skipped_gates.length} preferred {candidate.skipped_gates.length === 1 ? 'gate' : 'gates'} skipped
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
        {candidate.rationale ? (
          <div className="mt-2 text-xs italic text-slate-600">{candidate.rationale}</div>
        ) : null}
      </td>
      <td className="px-4 py-3 text-right text-sm text-slate-700">
        {formatMoney(candidate.take_profit, candidate.ticker)}
        {candidate.fair_value && candidate.fair_value_trust_flag === 'trusted' ? (
          <div className="mt-1 text-xs text-slate-600">
            fair value: {formatMoney(String(candidate.fair_value), candidate.ticker)}
            {candidate.fair_value_basis ? ` (${candidate.fair_value_basis})` : null}
          </div>
        ) : candidate.fair_value_trust_flag && candidate.fair_value_trust_flag !== 'trusted' ? (
          <div className="mt-1 text-xs text-slate-400">fair value: {candidate.fair_value_trust_flag}</div>
        ) : null}
      </td>
      <td className="px-4 py-3 text-sm text-slate-700">{candidate.reason}</td>
      <td className="px-4 py-3 text-sm text-slate-700">
        {candidate.entry_timing ? (
          <div className="min-w-0 space-y-2">
            <div className="flex flex-wrap items-center gap-2">
              <span className="border border-slate-300 px-2 py-0.5 text-xs font-semibold text-slate-900">
                {entryStateLabel(candidate.entry_timing.state)}
              </span>
              <span className="text-xs text-slate-600">{candidate.entry_timing.summary}</span>
            </div>
            <div className="flex flex-wrap gap-1">
              {candidate.entry_timing.components.map((component) => (
                <span
                  className={`border px-1.5 py-0.5 text-xs ${
                    component.status === 'pass'
                      ? 'border-emerald-200 bg-emerald-50 text-emerald-800'
                      : component.status === 'fail'
                        ? 'border-amber-200 bg-amber-50 text-amber-800'
                        : 'border-slate-200 bg-slate-50 text-slate-600'
                  }`}
                  key={component.name}
                  title={component.reason}
                >
                  {componentLabel(component.name)}
                </span>
              ))}
            </div>
            <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-slate-500">
              {candidate.entry_timing.diagnostics.pivot !== null &&
              candidate.entry_timing.diagnostics.pivot !== undefined ? (
                <span>pivot {candidate.entry_timing.diagnostics.pivot.toFixed(2)}</span>
              ) : null}
              {candidate.entry_timing.diagnostics.base_type &&
              candidate.entry_timing.diagnostics.base_type !== 'none' ? (
                <span>{candidate.entry_timing.diagnostics.base_type.replaceAll('_', '-')} base</span>
              ) : null}
              {candidate.entry_timing.diagnostics.breakout_volume_ratio !== null &&
              candidate.entry_timing.diagnostics.breakout_volume_ratio !== undefined ? (
                <span>{candidate.entry_timing.diagnostics.breakout_volume_ratio.toFixed(2)}x vol</span>
              ) : null}
            </div>
          </div>
        ) : (
          <span className="text-xs text-slate-400">-</span>
        )}
      </td>
      <td className="px-4 py-3 text-sm text-slate-700">
        <EventsBadge candidate={candidate} />
      </td>
      <td className="space-y-2 px-4 py-3 text-right">
        <AddToWatchlist
          candidate={candidate}
          strategySlug={strategySlug}
          buttonClassName="w-full border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-800 hover:bg-slate-100"
        />
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
