import { expect, test } from '@playwright/test';
import { isolatePortfolioState } from './_state';

/**
 * Feature 019 (US2): the transaction ledger + all entry/import/delete controls
 * live on a dedicated /transactions page; the Portfolio page carries none of
 * them, only a one-click link to /transactions (FR-001/FR-002, SC-003).
 */

const SEEDED_STATE = {
  state: {
    portfolio: {
      schema_version: 3,
      total_capital: 100000,
      holdings: [],
      created_at: '2026-06-11T00:00:00Z',
      updated_at: '2026-06-11T00:00:00Z',
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
      liquidity_min_avg_dollar_volume_20d: 1_000_000,
      liquidity_min_price: 5,
      exclude_earnings_within_days_overrides: {},
      default_strategy_slug: 'midterm_52w_high_momentum',
    },
    transactions: [
      {
        id: 'txn-nvda-1',
        ticker: 'NVDA',
        action: 'buy',
        quantity: '10',
        price: '100.00',
        trade_date: '2025-01-02',
        fees: null,
        note: null,
        source_row: 1,
      },
    ],
    sheet_id: null,
    sheet_range: null,
  },
  version: 3,
};

test.beforeEach(async ({ page }) => {
  await isolatePortfolioState(page);
  await page.addInitScript((value) => {
    localStorage.setItem('screener-storage', JSON.stringify(value));
  }, SEEDED_STATE);
});

test('transaction entry, import, and ledger live on /transactions', async ({ page }) => {
  await page.goto('/transactions');

  // Record-a-transaction form + Sheet import are both present.
  await expect(page.getByRole('heading', { name: 'Record a Transaction' })).toBeVisible();
  await expect(page.getByLabel('Transaction ticker')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Record transaction' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Import from Google Sheet' })).toBeVisible();

  // The seeded transaction shows in the chronological ledger with a Delete control.
  const ledgerRow = page.locator('tr', { hasText: 'NVDA' }).first();
  await expect(ledgerRow).toBeVisible();
  await expect(ledgerRow.getByRole('button', { name: 'Delete' })).toBeVisible();
});

test('Portfolio page has no transaction UI, only a link to /transactions', async ({ page }) => {
  await page.goto('/portfolio');

  // A one-click link to the Transactions page is present.
  const link = page.getByRole('link', { name: /transactions/i });
  await expect(link.first()).toBeVisible();

  // No transaction entry / import / ledger controls on the Portfolio page.
  await expect(page.getByRole('heading', { name: 'Record a Transaction' })).toHaveCount(0);
  await expect(page.getByRole('heading', { name: 'Import from Google Sheet' })).toHaveCount(0);
  await expect(page.getByLabel('Transaction ticker')).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Record transaction' })).toHaveCount(0);
});

test('Transactions nav link is present in the app shell', async ({ page }) => {
  await page.goto('/portfolio');
  await expect(
    page.getByRole('navigation', { name: 'Primary' }).getByRole('link', { name: 'Transactions' }),
  ).toBeVisible();
});
