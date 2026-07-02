import { expect, Page, test } from '@playwright/test';

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

const CANDIDATE = {
  ticker: 'ABC',
  name: 'ABC Co',
  sector: 'Technology',
  strategy_slug: 'midterm_52w_high_momentum',
  strategy_name: 'Mid-Term 52-Week High Momentum',
  timeframe: 'Mid-term',
  current_price: '12.00',
  entry: '12.00',
  stop_loss: '9.50',
  tighter_stop_loss: '10.50',
  take_profit: '19.50',
  rank: 1,
  score: 1,
  reason: 'Fixture match',
  gate_results: [],
  recent_8k_count_30d: 0,
};

function emptyStorage() {
  return {
    state: {
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
      transactions: [],
      sheet_id: null,
      sheet_range: null,
    },
    version: 6,
  };
}

async function seedStorage(page: Page) {
  await page.addInitScript((value) => {
    localStorage.setItem('screener-storage', JSON.stringify(value));
  }, emptyStorage());
}

async function mockWatchlistRoutes(page: Page) {
  let serverState: unknown = null;
  await page.route('**/portfolio/state', async (route) => {
    if (route.request().method() === 'PUT') {
      serverState = route.request().postDataJSON();
      await route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({ state: serverState, updated_at: '2026-07-02T21:00:00Z' }),
      });
      return;
    }
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ state: serverState, updated_at: serverState ? '2026-07-02T21:00:00Z' : null }),
    });
  });
  await page.route('**/strategies/midterm_52w_high_momentum', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        slug: 'midterm_52w_high_momentum',
        name: 'Mid-Term 52-Week High Momentum',
        timeframe: 'Mid-term',
        citation: 'Fixture citation',
        description: 'Fixture strategy',
        holding_period_days: { min: 30, max: 180 },
        parameters: {},
        regime_favorability: {},
        default_exclude_earnings_within_days: 0,
        enabled_by_default: true,
        modifications: [],
      }),
    });
  });
  await page.route('**/strategies/midterm_52w_high_momentum/backtest/equity-curve', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        strategy_slug: 'midterm_52w_high_momentum',
        points: [],
        data_sources: [],
        data_as_of: '2026-07-02T21:00:00Z',
        disclaimer: 'Fixture disclaimer',
      }),
    });
  });
  await page.route('**/strategies/midterm_52w_high_momentum/backtest', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        strategy_slug: 'midterm_52w_high_momentum',
        data_window_start: '2025-01-01',
        data_window_end: '2026-07-02',
        window_meets_v1_floor: true,
        limited_window_warning: null,
        data_sources: [],
        bias_check: [],
        yearly_metrics: [],
        summary_metrics: {
          total_return: 0,
          max_drawdown: 0,
          hit_rate: 0,
          avg_win: 0,
          avg_loss: 0,
          turnover: 0,
        },
        data_as_of: '2026-07-02T21:00:00Z',
        disclaimer: 'Fixture disclaimer',
      }),
    });
  });
  await page.route('**/strategies/midterm_52w_high_momentum/run', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        id: 'fixture-screen',
        strategy_slug: 'midterm_52w_high_momentum',
        as_of_date: '2026-07-02',
        parameters_snapshot: {},
        filters_snapshot: {},
        candidate_count: 1,
        candidates: [CANDIDATE],
        computed_at: '2026-07-02T21:00:00Z',
        data_as_of: '2026-07-02T21:00:00Z',
        disclaimer: 'Fixture disclaimer',
      }),
    });
  });
  await page.route('**/candidates/ABC**', async (route) => {
    if (route.request().url().includes('/history')) {
      await route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({
          ticker: 'ABC',
          points: [],
          source_name: 'fixture',
          source_as_of: '2026-07-02T21:00:00Z',
          data_as_of: '2026-07-02T21:00:00Z',
          disclaimer: 'Fixture disclaimer',
        }),
      });
      return;
    }
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        ticker: 'ABC',
        name: 'ABC Co',
        sector: 'Technology',
        current_price: '12.00',
        matches: [CANDIDATE],
        events: [],
        shariah: {
          ticker: 'ABC',
          is_compliant: false,
          source_kind: 'not_listed',
          external_source_name: null,
          external_source_as_of: null,
          is_stale: false,
          source_url: null,
          user_note: null,
          conflict: false,
          active_sources: ['spus_holdings'],
        },
        data_as_of: '2026-07-02T21:00:00Z',
        disclaimer: 'Fixture disclaimer',
      }),
    });
  });
  await page.route('**/analyze/ABC**', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        ...CANDIDATE,
        strategy: 'midterm_52w_high_momentum',
        as_of: '2026-07-02',
        would_be_selected: true,
        entry_timing: null,
        data_as_of: '2026-07-02T21:00:00Z',
        disclaimer: 'Fixture disclaimer',
      }),
    });
  });
}

test.beforeEach(async ({ page }) => {
  await seedStorage(page);
  await mockWatchlistRoutes(page);
});

test('adds candidates to the watchlist from table and detail with confirmation and no duplicate', async ({
  page,
}) => {
  await page.goto('/screen/midterm_52w_high_momentum');
  await page.getByRole('button', { name: 'Run screen' }).click();

  await page.getByRole('button', { name: 'Add to watchlist' }).click();
  await expect(page.getByText('Added to watchlist')).toBeVisible();
  await page.waitForFunction(() => {
    const raw = localStorage.getItem('screener-storage');
    if (!raw) return false;
    return JSON.parse(raw).state.watchlist.some(
      (entry: { ticker: string; strategy_slug: string }) =>
        entry.ticker === 'ABC' && entry.strategy_slug === 'midterm_52w_high_momentum',
    );
  });
  await page.waitForTimeout(900);

  await page.goto('/watchlist');
  await expect(page.getByTestId('watchlist-ticker')).toHaveText('ABC');
  await expect(page.getByText('Captured entry $12.00')).toBeVisible();
  await expect(page.getByText('stop $9.50')).toBeVisible();
  await expect(page.getByText('target $19.50')).toBeVisible();

  await page.goto('/candidate/ABC?strategy=midterm_52w_high_momentum');
  await expect(page.getByRole('button', { name: 'Already watched' })).toBeVisible();
  await page.getByRole('button', { name: 'Already watched' }).click();
  await expect(page.locator('[aria-live="polite"]').filter({ hasText: 'Already watched' })).toBeVisible();

  const count = await page.evaluate(() => {
    const raw = localStorage.getItem('screener-storage');
    return raw ? JSON.parse(raw).state.watchlist.length : 0;
  });
  expect(count).toBe(1);
});
