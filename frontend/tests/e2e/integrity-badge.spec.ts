import { expect, test } from '@playwright/test';

test('US4 and US5: Data integrity badge and momentum sign', async ({ page }) => {
  // Mock the screen run to return a flagged candidate and a negative momentum one.
  await page.route('**/strategies/midterm_52w_high_momentum/run', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        id: 'test-run',
        strategy_slug: 'midterm_52w_high_momentum',
        as_of_date: '2026-06-15',
        parameters_snapshot: {},
        filters_snapshot: {},
        candidate_count: 2,
        candidates: [
          {
            ticker: 'BAD',
            name: 'Bad Data Corp',
            sector: 'Technology',
            current_price: '100.00',
            entry: '100.00',
            stop_loss: '90.00',
            take_profit: '130.00',
            rank: 1,
            score: 0.95,
            reason: 'Match',
            return_12_1: -0.15,
            data_suspect: true,
            data_integrity_warnings: [
              { figure: 'close', rule: 'series_integrity', reason: 'unexplained single-session jump' }
            ],
            gate_results: []
          },
          {
            ticker: 'GOOD',
            name: 'Good Data Corp',
            sector: 'Technology',
            current_price: '50.00',
            entry: '50.00',
            stop_loss: '45.00',
            take_profit: '65.00',
            rank: 2,
            score: 0.90,
            reason: 'Match',
            return_12_1: 0.25,
            data_suspect: false,
            data_integrity_warnings: [],
            gate_results: []
          }
        ],
        computed_at: '2026-06-15T12:00:00Z',
        data_as_of: '2026-06-15',
        disclaimer: 'Disclaimer'
      })
    });
  });

  // Mock the strategies list so the page loads
  await page.route('**/strategies/midterm_52w_high_momentum', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        slug: 'midterm_52w_high_momentum',
        name: 'Mid-Term 52-Week High Momentum',
        timeframe: 'Mid-term',
        citation: 'George & Hwang (2004)',
        description: 'Description',
        holding_period_days: { min: 20, max: 60 },
        parameters: {},
        regime_favorability: {},
        default_exclude_earnings_within_days: 0,
        enabled_by_default: true,
        modifications: []
      })
    });
  });

  // Mock backtest to avoid errors
  await page.route('**/strategies/midterm_52w_high_momentum/backtest', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        data_as_of: '2026-06-15',
        data_sources: [{ source_name: 'Stooq' }],
        summary_metrics: { total_return: 0.2, max_drawdown: -0.1, hit_rate: 0.5, avg_win: 0.1, avg_loss: -0.05, turnover: 4.0 }
      })
    });
  });

  await page.goto('/screen/midterm_52w_high_momentum');
  await page.getByRole('button', { name: 'Run screen' }).click();

  // Check for the integrity badge on the BAD candidate
  const badRow = page.locator('tr').filter({ hasText: 'BAD' });
  await expect(badRow.getByText('🛑 DATA INTEGRITY')).toBeVisible();
  
  // Check for the negative momentum sign
  await expect(badRow.getByText('12-1 Mom: -15.0%')).toBeVisible();
  
  // Check for the positive momentum sign on the GOOD candidate
  const goodRow = page.locator('tr').filter({ hasText: 'GOOD' });
  await expect(goodRow.getByText('12-1 Mom: +25.0%')).toBeVisible();
  await expect(goodRow.getByText('🛑 DATA INTEGRITY')).not.toBeVisible();
});
