import { expect, test } from '@playwright/test';

test('home dashboard renders official market event categories', async ({ page }) => {
  await page.goto('/');

  await expect(page.getByRole('heading', { name: 'Market Events' })).toBeVisible();
  for (const label of ['FOMC', 'CPI', 'NFP', 'PCE', 'PPI']) {
    await expect(page.getByText(label).first()).toBeVisible();
  }
});

test('market events panel renders quickly when the source request fails', async ({ page }) => {
  await page.route('**/events/market**', (route) => route.abort());
  await page.goto('/');

  await expect(page.getByRole('heading', { name: 'Market Events' })).toBeVisible({ timeout: 1000 });
  await expect(page.getByText('Market events unavailable.')).toBeVisible({ timeout: 1000 });
});

test('candidate rows show earnings badges and earnings exclusion removes imminent rows', async ({ page }) => {
  await page.goto('/screen/shortterm_atr_breakout');
  await page.getByRole('button', { name: 'Run Screen' }).click();

  await expect(page.getByText(/Earnings in \d+ days/).first()).toBeVisible({ timeout: 45_000 });

  await page.getByLabel('Earnings exclusion days').fill('90');
  await page.getByRole('button', { name: 'Run Screen' }).click();

  await expect(page.getByText('0 matches')).toBeVisible({ timeout: 45_000 });
});

