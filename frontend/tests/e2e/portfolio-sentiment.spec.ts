import { test, expect, Page } from '@playwright/test';
import { isolatePortfolioState } from './_state';

// Feature 014 / US4 (T041): from the portfolio view the owner can select one or
// more holdings and run the SAME on-request sentiment report (reusing the US3
// engine + SentimentReport component). Selected holdings render a label +
// narrative (or "no signal"); unselected holdings are never analyzed.

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

function holding(ticker: string, sector: string) {
  return {
    ticker,
    shares: 10,
    avg_cost: 90,
    current_price: 100,
    sector,
    avg_dollar_volume_20d: 2_000_000,
    added_at: '2026-06-11T00:00:00Z',
  };
}

test('portfolio holdings can be selected and run through the on-request sentiment report', async ({ page }) => {
  await isolatePortfolioState(page);
  await seedStorage(page, {
    portfolio: {
      schema_version: 3,
      total_capital: 100000,
      holdings: [holding('AAPL', 'Information Technology'), holding('MSFT', 'Information Technology')],
      created_at: '2026-06-11T00:00:00Z',
      updated_at: '2026-06-11T00:00:00Z',
      local_storage_notice_acknowledged: true,
    },
    watchlist: [],
    settings: SETTINGS,
    transactions: [],
    sheet_id: null,
    sheet_range: null,
  });

  const requestBodies: { selections: { ticker: string; origin: string }[] }[] = [];
  await page.route('**/sentiment/report', async (route) => {
    const body = route.request().postDataJSON() as { selections: { ticker: string; origin: string }[] };
    requestBodies.push(body);
    const reports = body.selections.map((selection) => ({
      ticker: selection.ticker,
      origin: selection.origin,
      label: 'positive',
      label_basis: 'Fixture score from sourced headlines.',
      sentiment_composite: 0.3,
      narrative_risk: { score: 12, label: 'Low narrative activity', signals: [] },
      narrative: `${selection.ticker} recent sourced context: fixture narrative.`,
      narrative_source: 'template',
      budget_state: 'ok',
      source_classes_present: ['news'],
      source_classes_omitted: [],
      sources: [],
      fingerprint: 'sha256:fixture',
      resolution: null,
    }));
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        reports,
        period_spend_usd: '0',
        monthly_cap_usd: '5.00',
        data_as_of: '2026-07-02T21:00:00Z',
        disclaimer: 'Fixture disclaimer',
      }),
    });
  });

  await page.goto('/portfolio');
  await expect(page.locator('tr', { hasText: 'AAPL' })).toBeVisible();

  // Select only AAPL for the report; MSFT stays unselected.
  await page.getByLabel('Select AAPL for sentiment report').check();

  await page.getByRole('button', { name: /Run sentiment report/ }).click();
  await page.getByRole('button', { name: 'Run report' }).click();

  // Selected holding renders its label + narrative.
  await expect(page.getByText('AAPL recent sourced context')).toBeVisible();

  // Unselected holding was never analyzed.
  await expect(page.getByText('MSFT recent sourced context')).toHaveCount(0);
  expect(requestBodies).toHaveLength(1);
  expect(requestBodies[0].selections).toEqual([{ ticker: 'AAPL', origin: 'holding' }]);
});
