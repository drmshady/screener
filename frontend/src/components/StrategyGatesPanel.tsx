import type { Strategy } from '@/lib/api';
import { STATUS_TONES } from '@/lib/design';
import { HelpTooltip } from './HelpTooltip';

function pct(value: number) {
  return `${(value * 100).toFixed(1)}%`;
}

// Feature 012 US2: the per-strategy three-tier gate classification surfaced to
// the owner (mirrors backend screening/gate_tiers.GATE_TIERS for momentum).
// essential = a non-pass excludes; preferred = a non-pass is retained + demoted
// when expanded coverage is on; disqualifier = a positive detection excludes.
const GATE_TIERS: Record<string, { essential: string[]; preferred: string[]; disqualifier: string[] }> = {
  midterm_52w_high_momentum: {
    essential: ['Liquidity', 'Data integrity', '52-week-high proximity'],
    preferred: ['Market regime', 'Sector strength', 'Relative strength'],
    disqualifier: ['Climax-top exhaustion', 'Huge-gap breakout'],
  },
};

function GateTierMap({ slug }: { slug: string }) {
  const tiers = GATE_TIERS[slug];
  if (!tiers) return null;
  const rows: { tier: string; label: string; note: string; gates: string[] }[] = [
    { tier: 'essential', label: 'Essential', note: 'a non-pass excludes the name', gates: tiers.essential },
    {
      tier: 'preferred',
      label: 'Preferred',
      note: 'a non-pass is retained and demoted below all clean names when expanded coverage is on',
      gates: tiers.preferred,
    },
    { tier: 'disqualifier', label: 'Disqualifier', note: 'a positive detection excludes / forces not entry-ready', gates: tiers.disqualifier },
  ];
  return (
    <div className="border-b border-slate-200 px-4 py-3">
      <div className="text-sm font-semibold text-slate-950">Gate tiers (expanded coverage)</div>
      <p className="mt-1 text-xs text-slate-500">
        Coverage stays at today&apos;s strict gating unless &ldquo;Expanded coverage&rdquo; is enabled; no gate threshold changes.
      </p>
      <div className="mt-2 grid gap-2">
        {rows.map((row) => (
          <div className="text-sm" key={row.tier}>
            <span className="font-medium text-slate-800">{row.label}</span>
            <span className="text-xs text-slate-500"> — {row.note}</span>
            <div className="mt-1 flex flex-wrap gap-1">
              {row.gates.map((gate) => (
                <span className="border border-slate-300 px-2 py-0.5 text-xs text-slate-700" key={gate}>
                  {gate}
                </span>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function metricSummary(strategy: Strategy) {
  if (!strategy.backtest_summary) {
    return 'No committed backtest summary is attached to this strategy yet.';
  }
  return [
    `Total return ${pct(strategy.backtest_summary.total_return)}`,
    `max drawdown ${pct(strategy.backtest_summary.max_drawdown)}`,
    `hit rate ${pct(strategy.backtest_summary.hit_rate)}`,
  ].join(' | ');
}

export function StrategyGatesPanel({ strategy }: { strategy: Strategy }) {
  const holdingWindow = `${strategy.holding_period_days.min}-${strategy.holding_period_days.max} days`;
  const favorability = Object.entries(strategy.regime_favorability);

  return (
    <section className="space-y-3">
      <div>
        <h2 className="text-lg font-semibold text-slate-950">Strategy gates</h2>
        <p className="text-sm text-slate-600">{strategy.description}</p>
      </div>
      <div className="panel">
        <div className="border-b border-slate-200 px-4 py-3">
          <div className="flex items-center gap-1 text-sm font-semibold text-slate-950">
            Core methodology
            <HelpTooltip term="Walk-forward" />
          </div>
          <div className="text-sm text-slate-700">{strategy.description}</div>
          <div className="mt-1 text-xs text-slate-500">{strategy.citation}</div>
        </div>
        <div className="border-b border-slate-200 px-4 py-3">
          <div className="text-sm font-semibold text-slate-950">Holding period</div>
          <div className="text-sm text-slate-700">{holdingWindow}</div>
        </div>
        {strategy.modifications.map((modification) => (
          <div className="border-b border-slate-200 px-4 py-3" key={modification.name}>
            <div className="text-sm font-semibold text-slate-950">{modification.name}</div>
            <div className="text-sm text-slate-700">{modification.description}</div>
            <div className="mt-1 text-xs text-slate-500">{modification.citation}</div>
          </div>
        ))}
        <GateTierMap slug={strategy.slug} />
        <div className="border-b border-slate-200 px-4 py-3">
          <div className="text-sm font-semibold text-slate-950">Regime favorability</div>
          <div className="mt-2 grid gap-2">
            {favorability.map(([regime, value]) => (
              <div className="flex items-center justify-between gap-3 text-sm" key={regime}>
                <span className="text-slate-700">{regime}</span>
                <span
                  className={`border px-2 py-1 text-xs font-semibold ${
                    value === 'Favorable'
                      ? STATUS_TONES.success
                      : value === 'Unfavorable'
                        ? STATUS_TONES.danger
                        : STATUS_TONES.neutral
                  }`}
                >
                  {value}
                </span>
              </div>
            ))}
          </div>
        </div>
        <div className="px-4 py-3">
          <div className="flex items-center gap-1 text-sm font-semibold text-slate-950">
            Limitations
            <HelpTooltip term="Survivorship bias" />
          </div>
          <p className="mt-1 text-sm text-slate-700">
            {metricSummary(strategy)}. Results depend on data-source coverage, point-in-time fundamentals, and the committed test window.
          </p>
        </div>
      </div>
    </section>
  );
}
