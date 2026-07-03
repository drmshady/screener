"use client";

import type { PipelineBoardItem } from '@/lib/api';
import type { CumulativeHeat, SectorCluster } from '@/lib/pipeline';
import { STATUS_TONES } from '@/lib/design';

const FIT_BAND: Record<string, { label: string; tone: string }> = {
  strong_fit: { label: 'Strong fit', tone: STATUS_TONES.success },
  partial_fit: { label: 'Partial fit', tone: STATUS_TONES.info },
  poor_fit: { label: 'Weak fit', tone: STATUS_TONES.warning },
  blocked: { label: 'Blocked', tone: STATUS_TONES.neutral },
};

// Neutral, non-directive short labels for the facts that failed.
const FAILED_FACT_LABEL: Record<string, string> = {
  entry_ready: 'entry timing not ready',
  meaningful_size_survives: 'no meaningful size',
  heat_headroom_ok: 'heat near ceiling',
  sector_room_ok: 'sector near cap',
  not_overconcentrated: 'would concentrate',
  regime_allows_entries: 'regime unfavorable',
  reward_to_risk_ok: 'low reward-to-risk',
  cash_sufficient: 'cash-limited',
};

const ENTRY_STATE_LABEL: Record<string, string> = {
  entry_ready: 'Entry-ready',
  not_entry_ready: 'Not entry-ready',
  entry_undetermined: 'Timing undetermined',
};

function human(value: string | null | undefined): string {
  return value ? value.replace(/_/g, ' ') : '—';
}

function pct(value: number | null | undefined): string {
  return value === null || value === undefined ? '—' : `${(value * 100).toFixed(1)}%`;
}

export function ReadyFitList({
  items,
  cumulativeHeat,
  clusters,
}: {
  items: PipelineBoardItem[];
  cumulativeHeat: CumulativeHeat;
  clusters: SectorCluster[];
}) {
  if (items.length === 0) {
    return (
      <section className="panel space-y-2 p-5" data-testid="ready-fit-list">
        <h2 className="text-lg font-semibold text-slate-950">Ready &amp; fit</h2>
        <p className="text-sm text-slate-600">
          No momentum candidates are on the watchlist yet. Save momentum candidates from a
          screen to see how they fit your portfolio here.
        </p>
      </section>
    );
  }

  return (
    <section className="panel space-y-4 p-5" data-testid="ready-fit-list">
      <div className="flex items-baseline justify-between">
        <h2 className="text-lg font-semibold text-slate-950">Ready &amp; fit</h2>
        <span className="text-xs text-slate-500">Ranked by portfolio fit</span>
      </div>

      {clusters.length > 0 ? (
        <div
          className={`${STATUS_TONES.warning} border p-3 text-sm`}
          data-testid="sector-cluster-note"
        >
          Sector clustering:{' '}
          {clusters
            .map((cluster) => `${cluster.sector} (${cluster.tickers.join(', ')})`)
            .join('; ')}
          . Taking several at once would concentrate these sectors.
        </div>
      ) : null}

      <ul className="space-y-3">
        {items.map((item, index) => {
          const isBinding = cumulativeHeat.bindingIndex === index;
          const cumulative = cumulativeHeat.cumulativeAfter[index];

          if (item.skipped_reason) {
            return (
              <li
                key={item.ticker}
                className="border border-slate-200 p-3 text-sm"
                data-testid="fit-row"
              >
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-slate-950">{item.ticker}</span>
                  <span className={`inline-flex border px-2 py-1 text-xs ${STATUS_TONES.neutral}`}>
                    Skipped
                  </span>
                </div>
                <p className="mt-1 text-slate-600">{item.skipped_reason}</p>
              </li>
            );
          }

          const band = item.fit ? FIT_BAND[item.fit.fit_band] : FIT_BAND.blocked;
          const sizing = item.sizing_preview;

          return (
            <li
              key={item.ticker}
              className="space-y-2 border border-slate-200 p-3 text-sm"
              data-testid="fit-row"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <span className="text-base font-semibold text-slate-950">{item.ticker}</span>
                  <span className="text-xs text-slate-500">{item.sector}</span>
                </div>
                <div className="flex items-center gap-2">
                  {item.entry_timing_state ? (
                    <span className="inline-flex border border-slate-200 px-2 py-1 text-xs text-slate-700">
                      {ENTRY_STATE_LABEL[item.entry_timing_state] ?? item.entry_timing_state}
                    </span>
                  ) : null}
                  <span
                    className={`inline-flex border px-2 py-1 text-xs font-semibold ${band.tone}`}
                    data-testid="fit-band"
                  >
                    {band.label}
                  </span>
                </div>
              </div>

              {sizing ? (
                <dl className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                  <div>
                    <dt className="text-xs uppercase text-slate-500">Suggested</dt>
                    <dd className="font-semibold text-slate-950">
                      {sizing.suggested_shares} sh · ${sizing.suggested_position_value}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs uppercase text-slate-500">Binding</dt>
                    <dd className="font-semibold text-slate-950">{human(sizing.binding_constraint)}</dd>
                  </div>
                  <div>
                    <dt className="text-xs uppercase text-slate-500">Reward-to-risk</dt>
                    <dd className="font-semibold text-slate-950">
                      {sizing.reward_to_risk != null ? `${sizing.reward_to_risk.toFixed(1)}x` : '—'}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs uppercase text-slate-500">Heat after</dt>
                    <dd className="font-semibold text-slate-950">{pct(sizing.portfolio_heat_after_pct)}</dd>
                  </div>
                </dl>
              ) : null}

              {item.fit ? (
                <p className="text-slate-600">{item.fit.rationale}</p>
              ) : null}

              {item.fit && item.fit.failed_facts.length > 0 ? (
                <div className="flex flex-wrap gap-1">
                  {item.fit.failed_facts.map((fact) => (
                    <span
                      key={fact}
                      className="inline-flex border border-slate-200 bg-slate-50 px-2 py-0.5 text-xs text-slate-600"
                    >
                      {FAILED_FACT_LABEL[fact] ?? fact.replace(/_/g, ' ')}
                    </span>
                  ))}
                </div>
              ) : null}

              {cumulative != null ? (
                <div className="text-xs text-slate-500">
                  Cumulative heat if taken in order: {pct(cumulative)}
                </div>
              ) : null}

              {isBinding ? (
                <div
                  className={`${STATUS_TONES.warning} border p-2 text-xs`}
                  data-testid="cumulative-heat-marker"
                >
                  Taking candidates down to here would push portfolio heat past the ceiling.
                </div>
              ) : null}
            </li>
          );
        })}
      </ul>
    </section>
  );
}
