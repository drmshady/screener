import type { Strategy } from '@/lib/api';
import { STATUS_TONES } from '@/lib/design';
import { HelpTooltip } from './HelpTooltip';

function pct(value: number) {
  return `${(value * 100).toFixed(1)}%`;
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
