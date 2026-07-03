"use client";

import { STATUS_TONES } from '@/lib/design';

function pct(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

/**
 * Feature 016 (US1): a compact read-out of the aggregate open-risk (portfolio
 * heat) budget — how much of the ceiling the current holdings already use and
 * how much headroom remains for new entries. Presentation only; the numbers
 * come straight from the board response.
 */
export function HeatGauge({
  ceilingPct,
  headroomPct,
}: {
  ceilingPct: number;
  headroomPct: number;
}) {
  const usedPct = Math.max(ceilingPct - headroomPct, 0);
  const fill = ceilingPct > 0 ? Math.min(usedPct / ceilingPct, 1) : 0;
  const tight = headroomPct <= 0;

  return (
    <section className="panel space-y-3 p-5" data-testid="heat-gauge">
      <div className="flex items-baseline justify-between">
        <h2 className="text-lg font-semibold text-slate-950">Portfolio heat</h2>
        <span className={`inline-flex border px-2 py-1 text-xs font-semibold ${tight ? STATUS_TONES.warning : STATUS_TONES.info}`}>
          {tight ? 'At ceiling' : `${pct(headroomPct)} headroom`}
        </span>
      </div>
      <div className="h-3 w-full overflow-hidden rounded bg-slate-100">
        <div
          className={tight ? 'h-full bg-amber-500' : 'h-full bg-sky-500'}
          style={{ width: `${fill * 100}%` }}
        />
      </div>
      <dl className="grid grid-cols-3 gap-3 text-sm">
        <div className="border border-slate-200 p-3">
          <dt className="text-xs uppercase text-slate-500">Used</dt>
          <dd className="mt-1 font-semibold text-slate-950">{pct(usedPct)}</dd>
        </div>
        <div className="border border-slate-200 p-3">
          <dt className="text-xs uppercase text-slate-500">Headroom</dt>
          <dd className="mt-1 font-semibold text-slate-950">{pct(Math.max(headroomPct, 0))}</dd>
        </div>
        <div className="border border-slate-200 p-3">
          <dt className="text-xs uppercase text-slate-500">Ceiling</dt>
          <dd className="mt-1 font-semibold text-slate-950">{pct(ceilingPct)}</dd>
        </div>
      </dl>
    </section>
  );
}
