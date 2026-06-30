import { test, expect, Page } from '@playwright/test';
import { isolatePortfolioState } from './_state';

const ROUTES = [
  '/',
  '/screen/midterm_52w_high_momentum',
  '/screen/midterm_value_composite',
  '/analyze',
  '/candidate/HFRO',
  '/watchlist',
  '/portfolio',
  '/settings',
  '/help',
];

const FORBIDDEN_WORDS = [' Buy', ' Sell', 'Recommended', 'Strong buy'];

// Feature 004 / FR-014: the advisor-prompt preview is the ONE place that may
// carry directive framing, and only in personal-use mode where it is marked
// with `data-personal-use-prompt`. Exclude exactly that element from the lint;
// the rest of the page (all app chrome) must stay directive-free.
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

for (const route of ROUTES) {
  test(`no directive trading language found on ${route}`, async ({ page }) => {
    await page.goto(route);
    await expect(page.getByRole('navigation', { name: 'Primary' })).toBeVisible();
    await assertNoDirectiveCopy(page);
  });
}

// ---------------------------------------------------------------------------
// Feature 013 (T036): the import, holdings (sizing / breach-target), and
// watchlist entry-readiness surfaces only render with data, so the route sweep
// above never exercises their dynamic copy. Seed the store + stub the proxy so
// each new surface renders its directive-sensitive states, then lint them too.
// ---------------------------------------------------------------------------

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

function levelBlock(status: 'stop_breached' | 'target_reached') {
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
  };
}

test('no directive trading language on the imported-holdings sizing & breach/target surface', async ({ page }) => {
  await isolatePortfolioState(page);
  await seedStorage(page, {
    portfolio: {
      schema_version: 3,
      total_capital: 100000,
      holdings: [],
      created_at: '2026-06-11T00:00:00Z',
      updated_at: '2026-06-11T00:00:00Z',
      local_storage_notice_acknowledged: true,
    },
    watchlist: [],
    settings: SETTINGS,
    transactions: [
      {
        id: 'tx-1',
        ticker: 'TESTCO',
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
            ticker: 'TESTCO',
            net_quantity: '10',
            avg_cost: '100.00',
            cost_basis: '1000.00',
            earliest_buy_date: '2025-01-15',
            most_recent_buy_date: '2025-01-15',
            realized_pl: '0.00',
            status: 'open',
            priceable: true,
            sector: 'Technology',
            current_price: '110.00',
            unrealized_pl: '100.00',
            unrealized_pl_pct: 0.1,
            data_notes: [],
            data_as_of: '2026-06-11T21:00:00Z',
            levels: {
              original_plan: levelBlock('stop_breached'),
              current_condition: levelBlock('target_reached'),
            },
            risk: {
              recommended_shares: 8,
              recommended_value: '880.00',
              actual_shares: '10',
              actual_value: '1100.00',
              actual_capital_at_risk: '180.00',
              actual_capital_at_risk_pct: 0.0018,
              per_trade_risk_budget: '150.00',
              over_risk: true,
              binding_constraint: 'per_trade_budget',
              sizing_reasoning: 'Bounded by the per-trade risk budget.',
              fail_open: true,
            },
          },
        ],
        totals: {
          total_invested: '1100.00',
          total_capital_at_risk: '180.00',
          total_capital_at_risk_pct: 0.0018,
        },
        data_as_of: '2026-06-11T21:00:00Z',
        disclaimer: 'Fixture disclaimer',
      }),
    });
  });

  await page.goto('/portfolio');
  await expect(page.getByText('Imported Holdings')).toBeVisible();
  // Confirm the directive-sensitive dynamic copy actually rendered before linting.
  await expect(page.getByText('Stop breached')).toBeVisible();
  await expect(page.getByText('Target reached')).toBeVisible();
  await expect(page.getByText(/Over risk:/)).toBeVisible();

  await assertNoDirectiveCopy(page);
});

function analyzeBody(ticker: string, ready: boolean) {
  return {
    ticker,
    name: `${ticker} Co`,
    sector: 'Technology',
    strategy: 'midterm_52w_high_momentum',
    as_of: '2026-06-11',
    would_be_selected: ready,
    current_price: '100.00',
    entry: '100.00',
    stop_loss: '92.00',
    tighter_stop_loss: null,
    take_profit: '118.00',
    gate_results: [],
    entry_timing: ready
      ? {
          state: 'entry_ready',
          components: [
            { name: 'trend', status: 'pass', value: 1, reason: 'Above the 200-day average.' },
            { name: 'pivot_proximity', status: 'pass', value: 0.01, reason: 'Near the pivot.' },
          ],
          disqualifiers: [],
          diagnostics: {},
          summary: 'All entry-timing checks are currently met.',
        }
      : {
          state: 'not_entry_ready',
          components: [
            { name: 'pivot_proximity', status: 'fail', value: 0.2, reason: 'Price is far below the pivot.' },
            { name: 'base_maturity', status: 'fail', value: 2, reason: 'Base is too young.' },
          ],
          disqualifiers: [],
          diagnostics: {},
          summary: 'Two entry-timing checks are not yet met.',
        },
    data_as_of: '2026-06-11',
    disclaimer: 'Fixture disclaimer',
  };
}

test('no directive trading language on the watchlist entry-readiness surface', async ({ page }) => {
  await isolatePortfolioState(page);
  await seedStorage(page, {
    portfolio: {
      schema_version: 3,
      total_capital: 100000,
      holdings: [],
      created_at: '2026-06-11T00:00:00Z',
      updated_at: '2026-06-11T00:00:00Z',
      local_storage_notice_acknowledged: true,
    },
    watchlist: [
      {
        id: 'midterm_52w_high_momentum-READY',
        ticker: 'READY',
        name: 'Ready Co',
        sector: 'Technology',
        strategy_slug: 'midterm_52w_high_momentum',
        saved_at: '2026-06-10T00:00:00Z',
        state: 'saved',
        levels_snapshot: { entry: '100.00', stop_loss: '92.00', take_profit: '118.00' },
        last_entry_state: 'not_entry_ready',
      },
      {
        id: 'midterm_52w_high_momentum-WAIT',
        ticker: 'WAIT',
        name: 'Wait Co',
        sector: 'Industrials',
        strategy_slug: 'midterm_52w_high_momentum',
        saved_at: '2026-06-10T00:00:00Z',
        state: 'saved',
        levels_snapshot: { entry: '50.00', stop_loss: '46.00', take_profit: '59.00' },
      },
    ],
    settings: SETTINGS,
    transactions: [],
    sheet_id: null,
    sheet_range: null,
  });

  await page.route('**/analyze/READY**', async (route) => {
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify(analyzeBody('READY', true)) });
  });
  await page.route('**/analyze/WAIT**', async (route) => {
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify(analyzeBody('WAIT', false)) });
  });

  await page.goto('/watchlist');
  // Confirm both entry-readiness states + the "newly ready" flag rendered.
  await expect(page.getByText('Entry ready')).toBeVisible();
  await expect(page.getByText('Watching — not yet ready')).toBeVisible();
  await expect(page.getByText('Newly ready')).toBeVisible();

  await assertNoDirectiveCopy(page);
});
