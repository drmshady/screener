"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  LabelList,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import type {
  BacktestResponse,
  CandidateHistoryResponse,
  EquityCurveResponse,
  RegimeResponse,
} from '@/lib/api';
import { CHART_COLORS, STATUS_TONES } from '@/lib/design';

function pct(value: number) {
  return `${(value * 100).toFixed(1)}%`;
}

function money(value: string | number) {
  return `$${Number(value).toFixed(2)}`;
}

function compactMoney(value: number) {
  return `$${value.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}

function compactDate(value: string) {
  return value.slice(5);
}

export function EquityCurveCharts({
  backtest,
  curve,
}: {
  backtest: BacktestResponse;
  curve: EquityCurveResponse | null;
}) {
  const points = curve?.points ?? [];

  return (
    <section className="space-y-3">
      <div>
        <h2 className="text-lg font-semibold text-slate-950">Backtest charts</h2>
        <p className="text-sm text-slate-600">
          Equity is displayed by artifact step because the committed curve stores observation numbers, not trade dates.
        </p>
      </div>
      {!backtest.window_meets_v1_floor && backtest.limited_window_warning ? (
        <div className={`${STATUS_TONES.warning} border p-3 text-sm`}>
          {backtest.limited_window_warning}. Review this window with survivorship and data-availability caveats.
        </div>
      ) : (
        <div className="border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700">
          Backtests are point-in-time where data exists, but survivorship and source coverage can still affect historical interpretation.
        </div>
      )}
      <div className="chart-frame" data-testid="equity-curve-chart">
        {points.length === 0 ? (
          <div className="text-sm text-slate-600">No equity curve artifact is available for this strategy.</div>
        ) : (
          <LineChart data={points} height={260} margin={{ bottom: 8, left: 0, right: 24, top: 12 }} width={760}>
            <CartesianGrid stroke="#e2e8f0" />
            <XAxis dataKey="step" tick={{ fontSize: 12 }} />
            <YAxis tick={{ fontSize: 12 }} tickFormatter={(value) => `${Number(value).toFixed(1)}x`} />
            <Tooltip formatter={(value) => [`${Number(value).toFixed(2)}x`, 'Equity']} labelFormatter={(label) => `Step ${label}`} />
            <Line dataKey="equity" dot={false} name="Equity" stroke={CHART_COLORS.equity} strokeWidth={2.4} type="monotone" />
          </LineChart>
        )}
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <div className="chart-frame" data-testid="yearly-return-chart">
          <h3 className="mb-3 text-sm font-semibold text-slate-950">Yearly total return</h3>
          <BarChart data={backtest.yearly_metrics} height={220} margin={{ bottom: 8, left: 0, right: 24, top: 12 }} width={520}>
            <CartesianGrid stroke="#e2e8f0" />
            <XAxis dataKey="year" tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} tickFormatter={(value) => pct(Number(value))} />
            <Tooltip formatter={(value) => [pct(Number(value)), 'Total return']} />
            <Bar dataKey="total_return" name="Total return">
              {backtest.yearly_metrics.map((year) => (
                <Cell fill={year.total_return >= 0 ? CHART_COLORS.barSecondary : CHART_COLORS.barRisk} key={year.year} />
              ))}
            </Bar>
          </BarChart>
        </div>
        <div className="chart-frame" data-testid="yearly-risk-chart">
          <h3 className="mb-3 text-sm font-semibold text-slate-950">Hit rate and drawdown</h3>
          <BarChart data={backtest.yearly_metrics} height={220} margin={{ bottom: 8, left: 0, right: 24, top: 12 }} width={520}>
            <CartesianGrid stroke="#e2e8f0" />
            <XAxis dataKey="year" tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} tickFormatter={(value) => pct(Number(value))} />
            <Tooltip formatter={(value, name) => [pct(Number(value)), name]} />
            <Legend />
            <Bar dataKey="hit_rate" fill={CHART_COLORS.barPrimary} name="Hit rate" />
            <Bar dataKey="max_drawdown" fill={CHART_COLORS.barRisk} name="Max drawdown" />
          </BarChart>
        </div>
      </div>
      <p className="chart-meta">
        Source: {(curve?.data_sources ?? backtest.data_sources).map((source) => `${source.source_name} as of ${source.source_as_of.slice(0, 10)}`).join(', ')}.
        Data as of {(curve?.data_as_of ?? backtest.data_as_of).slice(0, 10)}.
      </p>
    </section>
  );
}

export function CandidatePriceChart({
  history,
  levels,
}: {
  history: CandidateHistoryResponse | null;
  levels: { entry: string; stop_loss: string; take_profit: string } | null;
}) {
  const points = history?.points ?? [];

  return (
    <section className="space-y-3">
      <div>
        <h2 className="text-lg font-semibold text-slate-950">Price history</h2>
        <p className="text-sm text-slate-600">Close, 52-week high, 200-day SMA, and active match reference levels.</p>
      </div>
      <div className="chart-frame" data-testid="candidate-price-chart">
        {points.length === 0 ? (
          <div className="text-sm text-slate-600">No local price history is available for this ticker.</div>
        ) : (
          <LineChart data={points} height={300} margin={{ bottom: 8, left: 0, right: 36, top: 12 }} width={840}>
            <CartesianGrid stroke="#e2e8f0" />
            <XAxis dataKey="date" minTickGap={28} tick={{ fontSize: 11 }} tickFormatter={compactDate} />
            <YAxis domain={['dataMin * 0.95', 'dataMax * 1.05']} tick={{ fontSize: 12 }} tickFormatter={(value) => money(Number(value))} />
            <Tooltip formatter={(value, name) => [money(Number(value)), name]} labelFormatter={(label) => `Date ${label}`} />
            <Legend />
            <Line dataKey="close" dot={false} name="Close" stroke={CHART_COLORS.price} strokeWidth={2.2} type="monotone" />
            <Line dataKey="sma_200" dot={false} name="200-day SMA" stroke={CHART_COLORS.sma} strokeDasharray="6 4" strokeWidth={1.8} type="monotone" />
            <Line dataKey="high_52w" dot={false} name="52-week high" stroke={CHART_COLORS.high} strokeDasharray="3 4" strokeWidth={1.8} type="monotone" />
            {levels ? (
              <>
                <ReferenceLine
                  ifOverflow="extendDomain"
                  label={{ value: 'Entry level', position: 'right', fill: CHART_COLORS.entry, fontSize: 12 }}
                  stroke={CHART_COLORS.entry}
                  strokeDasharray="4 3"
                  y={Number(levels.entry)}
                />
                <ReferenceLine
                  ifOverflow="extendDomain"
                  label={{ value: 'Stop level', position: 'right', fill: CHART_COLORS.stop, fontSize: 12 }}
                  stroke={CHART_COLORS.stop}
                  strokeDasharray="4 3"
                  y={Number(levels.stop_loss)}
                />
                <ReferenceLine
                  ifOverflow="extendDomain"
                  label={{ value: 'Target level', position: 'right', fill: CHART_COLORS.target, fontSize: 12 }}
                  stroke={CHART_COLORS.target}
                  strokeDasharray="4 3"
                  y={Number(levels.take_profit)}
                />
              </>
            ) : null}
          </LineChart>
        )}
      </div>
      {history ? (
        <p className="chart-meta">
          Source: {history.source_name} as of {history.source_as_of.slice(0, 10)}. Data as of {history.data_as_of.slice(0, 10)}.
        </p>
      ) : null}
    </section>
  );
}

export function RegimeVisual({ regime }: { regime: RegimeResponse }) {
  const spyClose = Number(regime.inputs.spy_close);
  const sma = Number(regime.inputs.spy_sma200);
  const spyPoints =
    Number.isFinite(spyClose) && Number.isFinite(sma)
      ? [
          { label: '200-day SMA', spy: sma, sma },
          { label: 'Latest', spy: spyClose, sma },
        ]
      : [];
  const breadth = regime.inputs.breadth_pct_above_sma200 ?? 0;

  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_280px]">
      <div className="chart-frame min-h-0" data-testid="regime-spy-chart">
        {spyPoints.length === 0 ? (
          <div className="text-sm text-slate-600">SPY trend inputs are unavailable.</div>
        ) : (
          <LineChart data={spyPoints} height={180} margin={{ bottom: 8, left: 0, right: 24, top: 12 }} width={500}>
            <CartesianGrid stroke="#e2e8f0" />
            <XAxis dataKey="label" tick={{ fontSize: 12 }} />
            <YAxis domain={['dataMin * 0.98', 'dataMax * 1.02']} tick={{ fontSize: 12 }} />
            <Tooltip formatter={(value, name) => [Number(value).toFixed(2), name]} />
            <Legend />
            <Line dataKey="spy" name="SPY close" stroke={CHART_COLORS.price} strokeWidth={2.2} />
            <Line dataKey="sma" name="200-day SMA" stroke={CHART_COLORS.sma} strokeDasharray="6 4" strokeWidth={1.8} />
          </LineChart>
        )}
      </div>
      <div className="panel p-4" data-testid="regime-breadth-gauge">
        <div className="text-sm font-semibold text-slate-950">Breadth bands</div>
        <div className="mt-4 h-4 border border-slate-300 bg-slate-100">
          <div className="h-full bg-teal-700" style={{ width: `${Math.max(0, Math.min(100, breadth * 100))}%` }} />
        </div>
        <div className="mt-2 grid grid-cols-3 text-xs text-slate-600">
          <span>40%</span>
          <span className="text-center">60%</span>
          <span className="text-right">{pct(breadth)}</span>
        </div>
        <div className="mt-3 text-xs text-slate-600">
          {regime.inputs.breadth_above_count}/{regime.inputs.breadth_eligible_count} eligible members above their 200-day SMA.
        </div>
      </div>
    </div>
  );
}

export function PortfolioAllocationChart({
  sectors,
  capPct,
}: {
  sectors: Array<{ sector: string; value: number; percentOfCapital: number; overCap: boolean }>;
  capPct: number;
}) {
  return (
    <div className="chart-frame" data-testid="portfolio-allocation-chart">
      {sectors.length === 0 ? (
        <div className="text-sm text-slate-600">No sector exposure yet.</div>
      ) : (
        <BarChart data={sectors} height={260} layout="vertical" margin={{ bottom: 8, left: 120, right: 40, top: 12 }} width={760}>
          <CartesianGrid stroke="#e2e8f0" />
          <XAxis tick={{ fontSize: 12 }} tickFormatter={(value) => pct(Number(value))} type="number" />
          <YAxis dataKey="sector" tick={{ fontSize: 12 }} type="category" width={120} />
          <Tooltip formatter={(value, name, item) => [name === 'percentOfCapital' ? pct(Number(value)) : compactMoney(Number(value)), item.payload.sector]} />
          <ReferenceLine
            label={{ value: `Sector cap ${pct(capPct)}`, position: 'top', fill: CHART_COLORS.cap, fontSize: 12 }}
            stroke={CHART_COLORS.cap}
            strokeDasharray="5 4"
            x={capPct}
          />
          <Bar dataKey="percentOfCapital" name="Capital share">
            {sectors.map((sector) => (
              <Cell fill={sector.overCap ? CHART_COLORS.barRisk : CHART_COLORS.barPrimary} key={sector.sector} />
            ))}
            <LabelList dataKey="percentOfCapital" formatter={(value) => pct(Number(value ?? 0))} position="right" />
          </Bar>
        </BarChart>
      )}
    </div>
  );
}
