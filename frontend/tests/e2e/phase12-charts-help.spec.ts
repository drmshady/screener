import { expect, test } from '@playwright/test';

function portfolioState() {
  const timestamp = '2026-06-11T00:00:00Z';
  return {
    state: {
      portfolio: {
        schema_version: 3,
        total_capital: 10000,
        holdings: [
          {
            ticker: 'MSFT',
            shares: 30,
            avg_cost: 90,
            current_price: 100,
            sector: 'Information Technology',
            avg_dollar_volume_20d: 2000000,
            added_at: timestamp,
          },
        ],
        created_at: timestamp,
        updated_at: timestamp,
        local_storage_notice_acknowledged: true,
      },
      watchlist: [],
      settings: {
        per_position_cap_pct: 0.1,
        per_sector_cap_pct: 0.25,
        shariah_filter_on: false,
        shariah_external_sources: ['spus_holdings'],
        shariah_user_inclusion: [],
        shariah_user_exclusion: [],
        liquidity_min_avg_dollar_volume_20d: 1000000,
        liquidity_min_price: 5,
        exclude_earnings_within_days_overrides: {},
        default_strategy_slug: 'midterm_52w_high_momentum',
      },
    },
    version: 3,
  };
}

test('strategy page mounts equity and yearly charts with citations', async ({ page }) => {
  await page.goto('/screen/midterm_52w_high_momentum');

  await expect(page.getByTestId('equity-curve-chart')).toBeVisible({ timeout: 45_000 });
  await expect(page.getByTestId('yearly-return-chart')).toBeVisible();
  await expect(page.getByTestId('yearly-risk-chart')).toBeVisible();
  await expect(page.getByText('George & Hwang (2004)').first()).toBeVisible();
  await expect(page.getByText('Limitations')).toBeVisible();
});

test('candidate page mounts price chart with level labels', async ({ page }) => {
  await page.goto('/candidate/HFRO');

  await expect(page.getByTestId('candidate-price-chart')).toBeVisible({ timeout: 45_000 });
  await expect(page.getByText('Entry level')).toBeVisible();
  await expect(page.getByText('Stop level')).toBeVisible();
  await expect(page.getByText('Target level')).toBeVisible();
});

test('home and portfolio mount regime and allocation visuals', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByTestId('regime-spy-chart')).toBeVisible({ timeout: 45_000 });
  await expect(page.getByTestId('regime-breadth-gauge')).toBeVisible();

  await page.addInitScript((value) => {
    localStorage.setItem('screener-storage', JSON.stringify(value));
  }, portfolioState());
  await page.goto('/portfolio');
  await expect(page.getByTestId('portfolio-allocation-chart')).toBeVisible();
  await expect(page.getByText('Sector cap 25.0%')).toBeVisible();
});

test('help page renders glossary, freshness, and strategy citations', async ({ page }) => {
  await page.goto('/help');

  await expect(page.getByRole('heading', { name: 'Glossary' })).toBeVisible();
  await expect(page.getByText('52-week high', { exact: true })).toBeVisible();
  await expect(page.getByText('Data sources and freshness')).toBeVisible();
  await expect(page.getByText('George & Hwang (2004)')).toBeVisible();
  await expect(page.getByLabel(/52-week high:/)).toBeVisible();
});
