import { expect, test } from '@playwright/test';

test('market events panel hides stale badge after reseed and labels schedule end', async ({ page }) => {
  await page.route('**/events/market**', (route) =>
    route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        events: [],
        source_name: 'econ_calendar_v1',
        source_as_of: '2026-06-11T00:00:00Z',
        is_stale: false,
        schedule_extends_through: '2027-06-09T18:00:00Z',
        data_as_of: '2026-07-02T21:00:00Z',
        disclaimer:
          'This product is for informational purposes only and does not constitute financial advice. It does not place trades.',
      }),
    }),
  );

  await page.goto('/');

  await expect(page.getByRole('heading', { name: 'Market Events' })).toBeVisible();
  await expect(page.getByText('Stale events data')).toHaveCount(0);
  await expect(page.getByText('Official schedule extends through Jun 9, 2027.')).toBeVisible();
});
