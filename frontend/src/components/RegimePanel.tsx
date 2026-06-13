"use client";

import { useEffect, useMemo, useState } from 'react';
import { RegimeResponse, RegimeResponseSchema, fetchApi } from '@/lib/api';
import { Abbr } from '@/components/Abbr';
import { STATUS_TONES } from '@/lib/design';
import { RegimeVisual } from './ChartPanels';

function inputNumber(value: string | number | null | undefined) {
  if (value === null || value === undefined) {
    return 'Unavailable';
  }
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) {
    return 'Unavailable';
  }
  return numeric.toFixed(2);
}

function percent(value: number | null | undefined) {
  if (value === null || value === undefined) {
    return 'Unavailable';
  }
  return `${(value * 100).toFixed(1)}%`;
}

function favorabilityClass(value: string) {
  if (value === 'Favorable') {
    return STATUS_TONES.success;
  }
  if (value === 'Unfavorable') {
    return STATUS_TONES.danger;
  }
  return STATUS_TONES.neutral;
}

export function RegimePanel() {
  const [regime, setRegime] = useState<RegimeResponse | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetchApi('/regime', RegimeResponseSchema)
      .then((response) => {
        if (!cancelled) {
          setRegime(response);
          setFailed(false);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setFailed(true);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const strategyRows = useMemo(() => regime?.per_strategy_favorability ?? [], [regime]);

  return (
    <section className="panel space-y-4 p-5">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="text-lg font-semibold text-slate-950">Market Regime</h2>
          {regime ? <div className="mt-1 text-sm text-slate-600">As of {regime.as_of_date}</div> : null}
        </div>
        {regime ? (
          <span className="inline-flex border border-slate-950 bg-slate-950 px-3 py-1 text-sm font-semibold text-white">
            {regime.regime}
          </span>
        ) : null}
      </div>

      {!regime && !failed ? <div className="text-sm text-slate-600">Loading regime...</div> : null}
      {failed ? <div className={`${STATUS_TONES.warning} border p-3 text-sm`}>Market regime unavailable.</div> : null}

      {regime ? (
        <>
          <p className="text-sm text-slate-700">{regime.rule_summary}</p>
          <RegimeVisual regime={regime} />
          <dl className="grid gap-3 text-sm sm:grid-cols-3">
            <div className="border border-slate-200 p-3">
              <dt className="text-xs uppercase text-slate-500">SPY close</dt>
              <dd className="mt-1 font-semibold text-slate-950">{inputNumber(regime.inputs.spy_close)}</dd>
            </div>
            <div className="border border-slate-200 p-3">
              <dt className="text-xs uppercase text-slate-500">SPY <Abbr term="SMA">SMA</Abbr> 200</dt>
              <dd className="mt-1 font-semibold text-slate-950">{inputNumber(regime.inputs.spy_sma200)}</dd>
            </div>
            <div className="border border-slate-200 p-3">
              <dt className="text-xs uppercase text-slate-500"><Abbr term="breadth">Breadth</Abbr> above <Abbr term="SMA">SMA</Abbr> 200</dt>
              <dd className="mt-1 font-semibold text-slate-950">{percent(regime.inputs.breadth_pct_above_sma200)}</dd>
              <dd className="mt-1 text-xs text-slate-600">
                {regime.inputs.breadth_above_count}/{regime.inputs.breadth_eligible_count} eligible, {regime.inputs.breadth_total_constituents} total
              </dd>
            </div>
          </dl>

          <div className="space-y-2">
            <h3 className="text-sm font-semibold text-slate-950">Strategy Favorability</h3>
            <div className="grid gap-2">
              {strategyRows.map((strategy) => (
                <div className="flex flex-col gap-2 border border-slate-200 p-3 sm:flex-row sm:items-center sm:justify-between" key={strategy.slug}>
                  <div>
                    <div className="text-sm font-medium text-slate-950">{strategy.name}</div>
                    <div className="text-xs text-slate-600">{strategy.slug}</div>
                  </div>
                  <span className={`inline-flex w-fit border px-2 py-1 text-xs font-semibold ${favorabilityClass(strategy.favorability)}`}>
                    {strategy.favorability}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </>
      ) : null}
    </section>
  );
}
