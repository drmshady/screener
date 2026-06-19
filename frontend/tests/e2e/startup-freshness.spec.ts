import { expect, test } from '@playwright/test';

const staleFreshness = {
  sources: [
    {
      source_name: 'yfinance',
      kind: 'prices',
      data_as_of: '2026-07-02',
      latest_session: '2026-07-06',
      sessions_behind: 1,
      is_stale: true,
      last_refresh_outcome: 'failed',
    },
  ],
  any_stale: true,
  latest_session: '2026-07-06',
  data_as_of: '2026-07-06T22:00:00Z',
  disclaimer: 'Informational only.',
};

const currentFreshness = {
  ...staleFreshness,
  sources: [
    {
      ...staleFreshness.sources[0],
      data_as_of: '2026-07-06',
      sessions_behind: 0,
      is_stale: false,
      last_refresh_outcome: 'skipped-current',
    },
  ],
  any_stale: false,
};

test('startup freshness prompt can refresh stale data', async ({ page }) => {
  let refreshed = false;
  await page.route('**/data/freshness', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify(refreshed ? currentFreshness : staleFreshness),
    });
  });
  await page.route('**/data/refresh', async (route) => {
    refreshed = true;
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        refreshed_tickers: 10,
        fetched_rows: 20,
        latest_bar: '2026-07-06',
        capped: false,
        notices: [],
        data_as_of: '2026-07-06T22:05:00Z',
        disclaimer: 'Informational only.',
      }),
    });
  });

  await page.goto('/');
  await expect(page.getByText('Cached data needs attention')).toBeVisible();
  await page.getByRole('button', { name: 'Refresh now' }).click();
  await expect(page.getByText('Data is current for latest completed session 2026-07-06.')).toBeVisible();
});

test('startup freshness prompt can proceed on cached data', async ({ page }) => {
  await page.route('**/data/freshness', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify(staleFreshness),
    });
  });

  await page.goto('/');
  await expect(page.getByText('Cached data needs attention')).toBeVisible();
  await page.getByRole('button', { name: 'Proceed on cached data' }).click();
  await expect(page.getByText(/Proceeding on cached data/)).toBeVisible();
  await expect(page.getByRole('link', { name: 'Screens' })).toBeVisible();
});
