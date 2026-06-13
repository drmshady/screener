import { test, expect } from '@playwright/test';
import { COPY } from '../../src/lib/copy';

const forbiddenWords = [' Buy', ' Sell', 'Recommended', 'Strong buy'];

async function expectSafePage(page, name: string) {
  await expect(page.locator(`text="${COPY.GLOBAL.DISCLAIMER}"`)).toBeVisible({ timeout: 45_000 });
  const bodyText = await page.evaluate(() => document.body.innerText);
  expect(bodyText).toMatch(/Data as of|As of|data_as_of/i);
  for (const word of forbiddenWords) {
    expect(bodyText.toLowerCase()).not.toContain(word.toLowerCase());
  }
  await page.screenshot({ path: `test-results/validation-${name}.png`, fullPage: true });
}

test('validation surface sweep covers primary pages', async ({ page }) => {
  await page.goto('/');
  await expectSafePage(page, 'home-events-regime');

  await page.goto('/screen/midterm_52w_high_momentum');
  await expect(page.getByRole('button', { name: /Run Screen/i })).toBeVisible({ timeout: 45_000 });
  await expectSafePage(page, 'midterm-screen');

  await page.goto('/candidate/EA');
  await expect(page.getByText('EA').first()).toBeVisible({ timeout: 45_000 });
  await expectSafePage(page, 'candidate-detail');

  await page.goto('/analyze');
  await page.getByLabel('Symbol').fill('EA');
  await page.getByRole('button', { name: /^Analyze$/ }).click();
  await expect(page.getByText('Gate checklist')).toBeVisible({ timeout: 45_000 });
  await expectSafePage(page, 'single-ticker-analysis');

  await page.goto('/portfolio');
  await expectSafePage(page, 'portfolio-sizing');

  await page.goto('/settings');
  await expect(page.getByText('Shariah').first()).toBeVisible();
  await expectSafePage(page, 'shariah-filter');

  await page.goto('/help');
  await expect(page.getByText('Backtest').first()).toBeVisible();
  await expectSafePage(page, 'backtest-help');
});
