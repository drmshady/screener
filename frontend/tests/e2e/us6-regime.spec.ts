import { expect, test } from '@playwright/test';

test('home dashboard renders regime and per-strategy favorability tags deterministically across reloads', async ({ page }) => {
  await page.goto('/');

  const panel = page.getByRole('heading', { name: 'Market Regime' }).locator('xpath=ancestor::section');
  await expect(panel.getByText(/^(Trending up|Range-bound|Trending down)$/)).toBeVisible({ timeout: 45_000 });
  await expect(panel.getByText('Strategy Favorability')).toBeVisible();
  await expect(panel.getByText('Mid-Term 52-Week High Momentum')).toBeVisible();
  await expect(panel.getByText('Short-Term Minervini VCP')).toBeVisible();
  await expect(panel.getByText('Short-Term ATR Breakout')).toBeVisible();
  await expect(panel.getByText(/Favorable|Neutral|Unfavorable/).first()).toBeVisible();
  await expect(panel.getByRole('term').filter({ hasText: 'SPY close' })).toBeVisible();
  await expect(panel.getByText('Breadth above SMA 200')).toBeVisible();

  const firstSnapshot = await panel.innerText();
  await page.reload();
  const reloadedPanel = page.getByRole('heading', { name: 'Market Regime' }).locator('xpath=ancestor::section');
  await expect(reloadedPanel.getByText(/^(Trending up|Range-bound|Trending down)$/)).toBeVisible({ timeout: 45_000 });
  expect(await reloadedPanel.innerText()).toBe(firstSnapshot);
});
