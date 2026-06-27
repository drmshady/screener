import { expect, test } from '@playwright/test';

test('analyze page renders pass fail and skip gate rows', async ({ page }) => {
  await page.route('**/strategies?enabled_only=false', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        strategies: [
          {
            slug: 'midterm_52w_high_momentum',
            name: 'Mid-Term 52-Week High Momentum',
            timeframe: 'Mid-term',
            citation: 'George & Hwang (2004)',
            description: 'Fixture strategy',
            holding_period_days: { min: 60, max: 180 },
            parameters: {},
            regime_favorability: {},
            default_exclude_earnings_within_days: 0,
            enabled_by_default: true,
            modifications: [],
          },
        ],
        data_as_of: '2026-06-11T21:00:00Z',
        disclaimer: 'Fixture disclaimer',
      }),
    });
  });
  await page.route('**/analyze/AAPL?strategy=midterm_52w_high_momentum', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        ticker: 'AAPL',
        name: 'Apple Inc.',
        sector: 'Information Technology',
        strategy: 'midterm_52w_high_momentum',
        as_of: '2026-06-11',
        would_be_selected: false,
        current_price: '200.00',
        entry: '200.00',
        stop_loss: '180.00',
        tighter_stop_loss: '190.00',
        take_profit: '260.00',
        gate_results: [
          { gate: '52-week-high proximity', status: 'pass', detail: '2.0% below the 52-week high' },
          { gate: 'Trend (above 200-day SMA)', status: 'fail', detail: 'close is at/below the 200-day SMA' },
          { gate: 'Sector strength', status: 'skipped', detail: 'needs universe context' },
        ],
        entry_timing: {
          state: 'not_entry_ready',
          components: [
            { name: 'pivot_proximity', status: 'pass', value: 0.02, reason: 'near pivot' },
            { name: 'trend', status: 'fail', value: 0, reason: 'at or below 200-day SMA' },
            { name: 'volume_confirmation', status: 'pass', value: 1.5, reason: 'confirming volume' },
            { name: 'base_maturity', status: 'pass', value: 6, reason: 'mature base' },
            { name: 'base_depth', status: 'pass', value: 0.18, reason: 'base depth in range' },
            { name: 'not_extended', status: 'pass', value: 0.13, reason: 'not extended from SMA-200' },
          ],
          disqualifiers: [],
          diagnostics: {
            pivot: 196,
            base_type: 'flat',
            base_length_weeks: 6,
            base_depth: 0.18,
            breakout_volume_ratio: 1.5,
            dist_above_pivot: 0.02,
            dist_above_sma_200: 0.13,
          },
          summary: 'at or below 200-day SMA',
        },
        data_notes: ['sector-strength percentile gate needs a full universe context'],
        data_as_of: '2026-06-11T21:00:00Z',
        disclaimer: 'Fixture disclaimer',
      }),
    });
  });

  await page.goto('/analyze');
  await page.getByRole('button', { name: 'Analyze' }).click();

  await expect(page.getByText('Would not match applied gates')).toBeVisible();
  await expect(page.getByText('PASS', { exact: true })).toBeVisible();
  await expect(page.getByText('FAIL', { exact: true })).toBeVisible();
  await expect(page.getByText('SKIP', { exact: true })).toBeVisible();
  await expect(page.getByText('Entry readiness')).toBeVisible();
  await expect(page.getByText('Not entry-ready')).toBeVisible();
  await expect(page.getByText('flat')).toBeVisible();
  await expect(page.getByText('sector-strength percentile gate needs a full universe context')).toBeVisible();
});
