import { render, screen } from '@testing-library/react';
import { describe, expect, test } from 'vitest';
import {
  CandidatePriceChart,
  EquityCurveCharts,
  PortfolioAllocationChart,
  RegimeVisual,
} from '../../src/components/ChartPanels';
import type {
  BacktestResponse,
  CandidateHistoryResponse,
  EquityCurveResponse,
  RegimeResponse,
} from '../../src/lib/api';

const backtest: BacktestResponse = {
  strategy_slug: 'midterm_52w_high_momentum',
  data_window_start: '2008-01-01',
  data_window_end: '2024-12-31',
  window_meets_v1_floor: true,
  limited_window_warning: null,
  data_sources: [{ source_name: 'Stooq', source_as_of: '2026-06-09T21:00:00Z' }],
  bias_check: [],
  yearly_metrics: [
    {
      year: 2024,
      trades: 4,
      hit_rate: 0.5,
      avg_win: 0.12,
      avg_loss: -0.05,
      total_return: 0.2,
      max_drawdown: -0.08,
    },
  ],
  summary_metrics: {
    total_return: 0.4,
    max_drawdown: -0.18,
    hit_rate: 0.55,
    avg_win: 0.11,
    avg_loss: -0.04,
    turnover: 1.2,
  },
  data_as_of: '2026-06-09T21:00:00Z',
  disclaimer: 'Informational only.',
};

describe('Phase 12 chart panels', () => {
  test('equity chart renders empty artifact state and source label', () => {
    render(<EquityCurveCharts backtest={backtest} curve={null} />);

    expect(screen.getByText('No equity curve artifact is available for this strategy.')).toBeTruthy();
    expect(screen.getByText(/Stooq as of 2026-06-09/)).toBeTruthy();
  });

  test('equity chart renders deterministic points when present', () => {
    const curve: EquityCurveResponse = {
      strategy_slug: backtest.strategy_slug,
      points: [
        { step: 1, equity: 1 },
        { step: 2, equity: 1.25 },
      ],
      data_window_start: backtest.data_window_start,
      data_window_end: backtest.data_window_end,
      data_sources: backtest.data_sources,
      data_as_of: backtest.data_as_of,
      disclaimer: backtest.disclaimer,
    };

    render(<EquityCurveCharts backtest={backtest} curve={curve} />);

    expect(screen.getByTestId('equity-curve-chart')).toBeTruthy();
    expect(screen.getByText('Yearly total return')).toBeTruthy();
    expect(screen.getByText('Hit rate and drawdown')).toBeTruthy();
  });

  test('candidate price chart exposes source/as-of labels', () => {
    const history: CandidateHistoryResponse = {
      ticker: 'HFRO',
      source_name: 'Stooq archive',
      source_as_of: '2026-06-09T21:00:00Z',
      data_as_of: '2026-06-09T21:00:00Z',
      disclaimer: 'Informational only.',
      points: [
        { date: '2026-06-08', close: 6.5, high: 6.7, low: 6.4, sma_200: 6.1, high_52w: 7.0 },
        { date: '2026-06-09', close: 6.8, high: 6.9, low: 6.6, sma_200: 6.2, high_52w: 7.0 },
      ],
    };

    render(
      <CandidatePriceChart
        history={history}
        levels={{ entry: '6.80', stop_loss: '6.10', take_profit: '7.50' }}
      />,
    );

    expect(screen.getByTestId('candidate-price-chart')).toBeTruthy();
    expect(screen.getByText(/Stooq archive as of 2026-06-09/)).toBeTruthy();
    expect(screen.getByText('Close')).toBeTruthy();
  });

  test('regime visual and allocation chart render graceful chart labels', () => {
    const regime: RegimeResponse = {
      regime: 'Trending up',
      rule_summary: 'SPY above its 200-day SMA.',
      inputs: {
        spy_close: 550,
        spy_sma200: 520,
        spy_above_sma200: true,
        breadth_pct_above_sma200: 0.62,
        breadth_above_count: 62,
        breadth_eligible_count: 100,
        breadth_total_constituents: 120,
        price_source_name: 'Stooq',
        breadth_source_name: 'Stooq',
        breadth_source_as_of: '2026-06-09T21:00:00Z',
      },
      as_of_date: '2026-06-09',
      per_strategy_favorability: [],
      data_as_of: '2026-06-09T21:00:00Z',
      disclaimer: 'Informational only.',
    };

    render(<RegimeVisual regime={regime} />);
    expect(screen.getByText('Breadth bands')).toBeTruthy();
    expect(screen.getByText('62/100 eligible members above their 200-day SMA.')).toBeTruthy();

    render(
      <PortfolioAllocationChart
        capPct={0.25}
        sectors={[{ sector: 'Information Technology', value: 3000, percentOfCapital: 0.3, overCap: true }]}
      />,
    );
    expect(screen.getByTestId('portfolio-allocation-chart')).toBeTruthy();
    expect(screen.getAllByText('Information Technology').length).toBeGreaterThan(0);
  });
});
