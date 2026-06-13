import { expect, test } from '@playwright/test';
import { isolatePortfolioState } from './_state';

test.beforeEach(async ({ page }) => {
  await isolatePortfolioState(page);
});

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

function storageWithHoldings(holdings: unknown[]) {
  return {
    state: {
      portfolio: {
        schema_version: 3,
        total_capital: 100000,
        holdings,
        created_at: '2026-06-11T00:00:00Z',
        updated_at: '2026-06-11T00:00:00Z',
        local_storage_notice_acknowledged: true,
      },
      watchlist: [],
      settings: SETTINGS,
    },
    version: 4,
  };
}

test('portfolio renders live quotes, levels, stale badge, and unrealized P/L', async ({ page }) => {
  await page.addInitScript((value) => {
    localStorage.setItem('screener-storage', JSON.stringify(value));
  }, storageWithHoldings([
    {
      ticker: 'ABC',
      shares: 10,
      avg_cost: 10,
      current_price: 9,
      sector: 'Technology',
      added_at: '2026-06-11T00:00:00Z',
    },
  ]));

  await page.route('**/shariah/status/ABC**', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
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
        data_as_of: '2026-06-11T21:00:00Z',
        disclaimer: 'Fixture disclaimer',
      }),
    });
  });
  await page.route('**/portfolio/quotes', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        quotes: [
          {
            ticker: 'ABC',
            name: 'ABC Co',
            sector: 'Technology',
            strategy_slug: 'midterm_52w_high_momentum',
            latest_price: '12.00',
            entry: '12.00',
            stop_loss: '9.50',
            tighter_stop_loss: '10.50',
            take_profit: '19.50',
            is_stale: true,
            data_notes: ['fixture stale quote'],
            data_as_of: '2026-06-11T21:00:00Z',
          },
        ],
        data_as_of: '2026-06-11T21:00:00Z',
        disclaimer: 'Fixture disclaimer',
      }),
    });
  });

  await page.goto('/portfolio');

  await expect(page.getByText('$12.00')).toBeVisible();
  await expect(page.getByRole('cell', { name: '$120.00' })).toBeVisible();
  await expect(page.getByText('$20.00')).toBeVisible();
  await expect(page.getByText('$9.50')).toBeVisible();
  await expect(page.getByText('$19.50')).toBeVisible();
  await expect(page.getByText('Stale quote')).toBeVisible();
});

test('candidate page adds a sized candidate to the local portfolio', async ({ page }) => {
  await page.addInitScript((value) => {
    localStorage.setItem('screener-storage', JSON.stringify(value));
  }, storageWithHoldings([]));

  await page.route('**/candidates/ABC**', async (route) => {
    if (route.request().url().includes('/history')) {
      await route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({
          ticker: 'ABC',
          points: [],
          source_name: 'fixture',
          source_as_of: '2026-06-11T21:00:00Z',
          data_as_of: '2026-06-11T21:00:00Z',
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
        matches: [
          {
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
          },
        ],
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
        data_as_of: '2026-06-11T21:00:00Z',
        disclaimer: 'Fixture disclaimer',
      }),
    });
  });
  await page.route('**/sizing', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        suggested_shares: 12,
        suggested_position_value: '144.00',
        resulting_position_pct_of_capital: 0.00144,
        resulting_sector_pct_of_capital: 0.00144,
        caps_respected: true,
        reasoning: 'Fixture sizing.',
        data_as_of: '2026-06-11T21:00:00Z',
        disclaimer: 'Fixture disclaimer',
      }),
    });
  });
  page.on('dialog', async (dialog) => {
    expect(dialog.defaultValue()).toBe('12');
    await dialog.accept('12');
  });

  await page.goto('/candidate/ABC');
  await expect(page.getByRole('button', { name: 'Add to portfolio' })).toBeVisible();
  await page.getByRole('button', { name: 'Add to portfolio' }).click();
  await page.waitForFunction(() => {
    const raw = localStorage.getItem('screener-storage');
    if (!raw) return false;
    return JSON.parse(raw).state.portfolio.holdings.length > 0;
  });

  const holding = await page.evaluate(() => {
    const raw = localStorage.getItem('screener-storage');
    return raw ? JSON.parse(raw).state.portfolio.holdings[0] : null;
  });
  expect(holding).toMatchObject({
    ticker: 'ABC',
    shares: 12,
    avg_cost: 12,
    current_price: 12,
    sector: 'Technology',
  });
});
