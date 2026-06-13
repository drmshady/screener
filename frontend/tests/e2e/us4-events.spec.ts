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

  // Baseline run shows at least one imminent-earnings badge (days < 90).
  await expect(page.getByText(/Earnings in \d+ days/).first()).toBeVisible({ timeout: 45_000 });
  const baselineDays = await page
    .getByText(/Earnings in \d+ days/)
    .allInnerTexts();
  expect(baselineDays.some((t) => Number(t.match(/(\d+)/)?.[1]) < 90)).toBeTruthy();

  // Excluding earnings within 90 days drops every name whose next earnings is
  // inside that window, so NO surviving badge may read fewer than 90 days. The
  // badge has no upper bound (it shows any future date), so we assert the
  // invariant on the numbers rather than expecting zero rows.
  await page.getByLabel('Earnings exclusion days').fill('90');
  await page.getByRole('button', { name: 'Run Screen' }).click();
  await expect(page.getByText(/\d+ matches for /).first()).toBeVisible({ timeout: 45_000 });

  await expect
    .poll(async () => {
      const texts = await page.getByText(/Earnings in \d+ days/).allInnerTexts();
      const days = texts.map((t) => Number(t.match(/(\d+)/)?.[1] ?? '0'));
      return days.every((d) => d >= 90); // true (vacuously) once imminent rows are gone
    })
    .toBeTruthy();
});

