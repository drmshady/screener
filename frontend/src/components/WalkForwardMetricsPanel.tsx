import type { BacktestResponse } from '@/lib/api';

function pct(value: number) {
  return `${(value * 100).toFixed(1)}%`;
}

export function WalkForwardMetricsPanel({ backtest }: { backtest: BacktestResponse }) {
  return (
    <section className="space-y-3">
      <div>
        <h2 className="text-lg font-semibold text-slate-950">Walk-forward metrics</h2>
        <p className="text-sm text-slate-600">
          {backtest.data_window_start} to {backtest.data_window_end} from {backtest.data_sources.map((source) => source.source_name).join(', ')}
        </p>
        <div className="mt-2 flex flex-wrap gap-2">
          {backtest.data_sources.map((source) => (
            <span className="border border-slate-200 bg-white px-2 py-1 text-xs text-slate-600" key={`${source.source_name}-${source.source_as_of}`}>
              {source.source_name} as of {source.source_as_of.slice(0, 10)}
            </span>
          ))}
        </div>
      </div>
      {!backtest.window_meets_v1_floor && backtest.limited_window_warning ? (
        <div className="border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          {backtest.limited_window_warning}
        </div>
      ) : null}
      {backtest.coverage_notes?.length ? (
        <div className="border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          <p className="font-medium">Backtest coverage limitations</p>
          <ul className="mt-1 list-disc pl-5">
            {backtest.coverage_notes.map((note) => (
              <li key={note}>{note}</li>
            ))}
          </ul>
        </div>
      ) : null}
      <div className="grid gap-3 sm:grid-cols-4">
        <div className="panel p-3">
          <div className="text-xs uppercase text-slate-500">Total return</div>
          <div className="text-xl font-semibold">{pct(backtest.summary_metrics.total_return)}</div>
        </div>
        <div className="panel p-3">
          <div className="text-xs uppercase text-slate-500">Max drawdown</div>
          <div className="text-xl font-semibold">{pct(backtest.summary_metrics.max_drawdown)}</div>
        </div>
        <div className="panel p-3">
          <div className="text-xs uppercase text-slate-500">Hit rate</div>
          <div className="text-xl font-semibold">{pct(backtest.summary_metrics.hit_rate)}</div>
        </div>
        <div className="panel p-3">
          <div className="text-xs uppercase text-slate-500">Turnover</div>
          <div className="text-xl font-semibold">{backtest.summary_metrics.turnover.toFixed(1)}x</div>
        </div>
      </div>
      {backtest.yearly_metrics.some((year) => year.reliability === 'low_sample') ? (
        <p className="text-xs text-slate-500">
          Years marked <span className="font-medium text-amber-800">thin sample</span> had few
          trades, so their per-year figures are less reliable.
        </p>
      ) : null}
      <div className="overflow-x-auto border border-slate-200 bg-white">
        <table className="data-table text-sm">
          <thead className="text-left">
            <tr>
              <th className="px-4 py-2 font-semibold">Year</th>
              <th className="px-4 py-2 font-semibold">Trades</th>
              <th className="px-4 py-2 font-semibold">Hit rate</th>
              <th className="px-4 py-2 font-semibold">Avg win</th>
              <th className="px-4 py-2 font-semibold">Avg loss</th>
              <th className="px-4 py-2 font-semibold">Max DD</th>
            </tr>
          </thead>
          <tbody>
            {backtest.yearly_metrics.map((year) => {
              const thin = year.reliability === 'low_sample';
              return (
                <tr className={thin ? 'bg-amber-50 text-amber-900' : undefined} key={year.year}>
                  <td className="px-4 py-2">{year.year}</td>
                  <td className="px-4 py-2">
                    {year.trade_count ?? year.trades}
                    {thin ? (
                      <span
                        className="ml-2 border border-amber-300 bg-amber-100 px-1.5 py-0.5 text-xs font-medium text-amber-800"
                        title="Few trades this year — figures are less reliable."
                      >
                        thin sample
                      </span>
                    ) : null}
                  </td>
                  <td className="px-4 py-2">{pct(year.hit_rate)}</td>
                  <td className="px-4 py-2">{pct(year.avg_win)}</td>
                  <td className="px-4 py-2">{pct(year.avg_loss)}</td>
                  <td className="px-4 py-2">{pct(year.max_drawdown)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}
