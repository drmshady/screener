import { test, expect, Page } from '@playwright/test';
import { isolatePortfolioState } from './_state';

// Feature 015 (US7 / T030): the new risk facts — a trailing `gains_protected`
// level, portfolio-heat headroom, and thin-sample walk-forward years — must
// render in neutral, zero-directive language and keep `data_as_of` + disclaimer.

const FORBIDDEN_WORDS = [' Buy', ' Sell', 'Recommended', 'Strong buy'];

async function assertNoDirectiveCopy(page: Page) {
  const bodyText = await page.evaluate(() => {
    const clone = document.body.cloneNode(true) as HTMLElement;
    clone.querySelectorAll('[data-personal-use-prompt]').forEach((el) => el.remove());
    return clone.innerText;
  });
  for (const word of FORBIDDEN_WORDS) {
    expect(bodyText.toLowerCase()).not.toContain(word.toLowerCase());
  }
}

const GLOBAL_DISCLAIMER =
  'This product is for informational purposes only and does not constitute financial advice.';

const SETTINGS = {
  per_position_cap_pct: 0.1,
  per_sector_cap_pct: 0.25,
  shariah_filter_on: false,
  shariah_external_sources: ['spus_holdings'],
  shariah_user_inclusion: [],
  shariah_user_exclusion: [],
  liquidity_min_avg_dollar_volume_20d: 1_000_000,
  liquidity_min_price: 5,
  exclude_earnings_within_days_overrides: {},
  default_strategy_slug: 'midterm_52w_high_momentum',
};

function seedStorage(page: Page, state: Record<string, unknown>) {
  return page.addInitScript((value) => {
    localStorage.setItem('screener-storage', JSON.stringify(value));
  }, { state, version: 6 });
}

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

test('trailing gains-protected level + portfolio-heat headroom render non-directively', async ({ page }) => {
  await isolatePortfolioState(page);
  await seedStorage(page, {
    portfolio: {
      schema_version: 3,
      total_capital: 100000,
      holdings: [],
      created_at: '2026-07-02T00:00:00Z',
      updated_at: '2026-07-02T00:00:00Z',
      local_storage_notice_acknowledged: true,
    },
    watchlist: [],
    settings: SETTINGS,
    transactions: [
      {
        id: 'tx-1',
        ticker: 'WINNER',
        action: 'buy',
        quantity: '10',
        price: '100.00',
        trade_date: '2025-01-15',
        fees: '1.00',
        note: null,
        source_row: 2,
      },
    ],
    sheet_id: 'sheet-abc',
    sheet_range: 'Transactions!A1:I',
  });

  await page.route('**/portfolio/holdings', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        holdings: [
          {
            ticker: 'WINNER',
            net_quantity: '10',
            avg_cost: '100.00',
            cost_basis: '1000.00',
            earliest_buy_date: '2025-01-15',
            most_recent_buy_date: '2025-01-15',
            realized_pl: '0.00',
            status: 'open',
            priceable: true,
            sector: 'Technology',
            current_price: '152.10',
            unrealized_pl: '521.00',
            unrealized_pl_pct: 0.52,
            data_notes: [],
            data_as_of: '2026-07-02T21:00:00Z',
            levels: {
              original_plan: levelBlock('holding'),
              current_condition: levelBlock('holding'),
              trailing: levelBlock('gains_protected', {
                entry: '152.10',
                stop_loss: '138.40',
                take_profit: null,
                distance_to_stop_pct: -0.09,
              }),
            },
            risk: {
              recommended_shares: 8,
              recommended_value: '1216.80',
              actual_shares: '10',
              actual_value: '1521.00',
              actual_capital_at_risk: '137.00',
              actual_capital_at_risk_pct: 0.00137,
              per_trade_risk_budget: '150.00',
              over_risk: false,
              binding_constraint: null,
              sizing_reasoning: 'Within the per-trade risk budget.',
              fail_open: false,
            },
          },
        ],
        totals: {
          total_invested: '1521.00',
          total_capital_at_risk: '137.00',
          total_capital_at_risk_pct: 0.045,
          heat_ceiling_pct: 0.06,
          heat_headroom_pct: 0.015,
        },
        data_as_of: '2026-07-02T21:00:00Z',
        disclaimer: 'Fixture disclaimer',
      }),
    });
  });

  await page.goto('/portfolio');
  await expect(page.getByText('Imported Holdings')).toBeVisible();
  await expect(page.getByText('Gains protected')).toBeVisible();
  await expect(page.getByText('Portfolio-heat headroom')).toBeVisible();
  await expect(page.getByRole('columnheader', { name: 'Trailing' })).toBeVisible();
  await expect(page.getByText(GLOBAL_DISCLAIMER)).toBeVisible();

  await assertNoDirectiveCopy(page);
});

test('walk-forward thin-sample years render non-directively with disclaimer', async ({ page }) => {
  await page.route('**/strategies/midterm_52w_high_momentum/backtest', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
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
            trades: 40,
            trade_count: 40,
            reliability: 'ok',
            hit_rate: 0.55,
            avg_win: 0.12,
            avg_loss: 0.06,
            total_return: 0.18,
            max_drawdown: 0.09,
          },
          {
            year: 2020,
            trades: 3,
            trade_count: 3,
            reliability: 'low_sample',
            hit_rate: 0.33,
            avg_win: 0.1,
            avg_loss: 0.08,
            total_return: -0.02,
            max_drawdown: 0.2,
          },
        ],
        summary_metrics: {
          total_return: 0.5,
          max_drawdown: 0.2,
          hit_rate: 0.55,
          avg_win: 0.12,
          avg_loss: 0.06,
          turnover: 100,
        },
        computed_at: '2026-07-02T21:00:00Z',
        data_as_of: '2024-12-31',
        disclaimer: 'Fixture disclaimer',
      }),
    });
  });

  await page.goto('/screen/midterm_52w_high_momentum');
  await expect(page.getByText('Walk-forward metrics')).toBeVisible();
  await expect(page.getByText('thin sample').first()).toBeVisible();
  await expect(page.getByText(GLOBAL_DISCLAIMER)).toBeVisible();

  await assertNoDirectiveCopy(page);
});
