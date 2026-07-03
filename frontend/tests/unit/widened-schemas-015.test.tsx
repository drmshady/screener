import { describe, expect, test } from 'vitest';

import {
  BacktestResponseSchema,
  HoldingLevelsSchema,
  LevelBlockSchema,
  PortfolioHoldingsResponseSchema,
  SizingResponseSchema,
} from '../../src/lib/api';

// Feature 015 (US7 / T029): the additive backend fields (trailing block,
// `gains_protected` status, portfolio-heat totals, `reward_to_risk`,
// `conservative_fallback`, per-year `reliability`) must parse, AND older payloads
// that predate them must still validate (backward-compatible optionals).

function levelBlock(status: string, overrides: Record<string, unknown> = {}) {
  return {
    entry: '100.00',
    stop_loss: '92.00',
    tighter_stop_loss: null,
    take_profit: '118.00',
    risk_distance: '8.00',
    reward_distance: '18.00',
    reward_ceiling_basis: 'volatility',
    bounds_applied: [],
    levels_state: 'ok',
    rationale: 'Bounded by volatility over the holding horizon.',
    distance_to_stop_pct: 0.05,
    distance_to_target_pct: 0.18,
    status,
    ...overrides,
  };
}

describe('feature 015 widened schemas (US7)', () => {
  test('LevelBlock accepts the new gains_protected status', () => {
    const parsed = LevelBlockSchema.parse(levelBlock('gains_protected'));
    expect(parsed.status).toBe('gains_protected');
  });

  test('HoldingLevels accepts a trailing block and older payloads without one', () => {
    const withTrailing = HoldingLevelsSchema.parse({
      original_plan: levelBlock('holding'),
      current_condition: levelBlock('holding'),
      trailing: levelBlock('gains_protected', { stop_loss: '138.40', entry: '152.10' }),
    });
    expect(withTrailing.trailing?.status).toBe('gains_protected');

    const legacy = HoldingLevelsSchema.parse({
      original_plan: levelBlock('holding'),
      current_condition: levelBlock('holding'),
    });
    expect(legacy.trailing ?? null).toBeNull();
  });

  test('PortfolioHoldingsResponse totals carry heat ceiling + headroom (optional)', () => {
    const parsed = PortfolioHoldingsResponseSchema.parse({
      holdings: [],
      totals: {
        total_invested: '40000.00',
        total_capital_at_risk: '1800.00',
        total_capital_at_risk_pct: 0.045,
        heat_ceiling_pct: 0.06,
        heat_headroom_pct: 0.015,
      },
      data_as_of: '2026-07-02T21:00:00Z',
      disclaimer: 'Fixture disclaimer',
    });
    expect(parsed.totals.heat_ceiling_pct).toBeCloseTo(0.06);
    expect(parsed.totals.heat_headroom_pct).toBeCloseTo(0.015);

    // Older payload without heat fields still validates.
    const legacy = PortfolioHoldingsResponseSchema.parse({
      holdings: [],
      totals: {
        total_invested: '40000.00',
        total_capital_at_risk: '1800.00',
        total_capital_at_risk_pct: 0.045,
      },
      data_as_of: '2026-07-02T21:00:00Z',
      disclaimer: 'Fixture disclaimer',
    });
    expect(legacy.totals.total_invested).toBe('40000.00');
  });

  test('SizingResponse carries reward-to-risk, heat-after, and conservative fallback', () => {
    const parsed = SizingResponseSchema.parse({
      suggested_shares: 20,
      suggested_position_value: '2000.00',
      resulting_position_pct_of_capital: 0.02,
      resulting_sector_pct_of_capital: 0.05,
      caps_respected: true,
      reasoning: 'Binding constraint: portfolio heat.',
      binding_constraint: 'portfolio_heat',
      conservative_fallback: false,
      reward_to_risk: 2.6,
      portfolio_heat_after_pct: 0.052,
      data_as_of: '2026-07-02T21:00:00Z',
      disclaimer: 'Fixture disclaimer',
    });
    expect(parsed.binding_constraint).toBe('portfolio_heat');
    expect(parsed.reward_to_risk).toBeCloseTo(2.6);
    expect(parsed.portfolio_heat_after_pct).toBeCloseTo(0.052);

    // Older payload without the new sizing fields still validates.
    const legacy = SizingResponseSchema.parse({
      suggested_shares: 10,
      suggested_position_value: '1000.00',
      resulting_position_pct_of_capital: 0.01,
      resulting_sector_pct_of_capital: 0.03,
      caps_respected: true,
      reasoning: 'Within configured limits.',
      data_as_of: '2026-07-02T21:00:00Z',
      disclaimer: 'Fixture disclaimer',
    });
    expect(legacy.conservative_fallback).toBe(false);
    expect(legacy.reward_to_risk ?? null).toBeNull();
  });

  test('Backtest yearly metrics carry the per-year reliability flag (optional)', () => {
    const parsed = BacktestResponseSchema.parse({
      strategy_slug: 'midterm_52w_high_momentum',
      data_window_start: '2008-01-01',
      data_window_end: '2024-12-31',
      window_meets_v1_floor: true,
      limited_window_warning: null,
      data_sources: [{ source_name: 'Stooq', source_as_of: '2024-12-31' }],
      bias_check: [{ item: 'costs', passed: true, note: 'modeled: 10 bps/side' }],
      coverage_notes: [],
      rebalance_cadence: 'Q',
      cost_model: { per_side_bps: 10, applied: true },
      yearly_metrics: [
        {
          year: 2015,
          trades: 7,
          trade_count: 7,
          reliability: 'low_sample',
          hit_rate: 0.5,
          avg_win: 0.1,
          avg_loss: 0.05,
          total_return: 0.12,
          max_drawdown: 0.08,
        },
      ],
      summary_metrics: {
        total_return: 0.5,
        max_drawdown: 0.2,
        hit_rate: 0.55,
        avg_win: 0.1,
        avg_loss: 0.05,
        turnover: 100,
      },
      data_as_of: '2024-12-31',
      disclaimer: 'Fixture disclaimer',
    });
    expect(parsed.yearly_metrics[0].reliability).toBe('low_sample');
    expect(parsed.rebalance_cadence).toBe('Q');
    expect(parsed.cost_model?.applied).toBe(true);

    // Older payload without reliability/cadence/cost_model still validates.
    const legacy = BacktestResponseSchema.parse({
      strategy_slug: 'midterm_52w_high_momentum',
      data_window_start: '2008-01-01',
      data_window_end: '2024-12-31',
      window_meets_v1_floor: true,
      limited_window_warning: null,
      data_sources: [{ source_name: 'Stooq', source_as_of: '2024-12-31' }],
      bias_check: [{ item: 'costs', passed: false, note: 'not included' }],
      yearly_metrics: [
        {
          year: 2015,
          trades: 7,
          hit_rate: 0.5,
          avg_win: 0.1,
          avg_loss: 0.05,
          total_return: 0.12,
          max_drawdown: 0.08,
        },
      ],
      summary_metrics: {
        total_return: 0.5,
        max_drawdown: 0.2,
        hit_rate: 0.55,
        avg_win: 0.1,
        avg_loss: 0.05,
        turnover: 100,
      },
      data_as_of: '2024-12-31',
      disclaimer: 'Fixture disclaimer',
    });
    expect(legacy.yearly_metrics[0].reliability ?? null).toBeNull();
  });
});
