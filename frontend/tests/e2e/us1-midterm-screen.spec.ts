import { expect, test } from '@playwright/test';
import { COPY } from '../../src/lib/copy';

test('US1 mid-term screen renders gates, metrics, candidates, and disclaimer', async ({ page }) => {
  await page.goto('/screen/midterm_52w_high_momentum');

  await expect(page.getByRole('heading', { name: 'Mid-Term 52-Week High Momentum' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Strategy gates' })).toBeVisible();
  await expect(page.getByText('George & Hwang (2004)')).toBeVisible();
  await expect(page.getByText('Barroso & Santa-Clara')).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Walk-forward metrics' })).toBeVisible();
  await expect(page.getByText(COPY.GLOBAL.DISCLAIMER)).toBeVisible();

  await page.getByRole('button', { name: COPY.SCREENER.RUN_SCREEN }).click();

  await expect(page.getByRole('heading', { name: 'Candidates' })).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText(/matches for \d{4}-\d{2}-\d{2}/)).toBeVisible();
  const candidates = page.locator('section').filter({ has: page.getByRole('heading', { name: 'Candidates' }) });
  const rows = candidates.locator('tbody tr');
  await expect(rows.first()).toBeVisible();
  await expect(rows.first().locator('td').nth(3)).toContainText('$');
  await expect(rows.first().locator('td').nth(4)).toContainText('$');
  await expect(rows.first().locator('td').nth(5)).toContainText('$');
  await expect(page.getByRole('button', { name: 'Save' }).first()).toBeVisible();
});
