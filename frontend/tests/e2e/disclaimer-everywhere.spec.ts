import { test, expect } from '@playwright/test';
import { COPY } from '../../src/lib/copy';

const ROUTES = [
  '/',
  '/screen/midterm_52w_high_momentum',
  '/sentiment',
  '/candidate/HFRO',
  '/watchlist',
  '/portfolio',
  '/settings',
  '/help',
];

for (const route of ROUTES) {
  test(`disclaimer is visible on ${route}`, async ({ page }) => {
    await page.goto(route);
    await expect(page.locator(`text="${COPY.GLOBAL.DISCLAIMER}"`)).toBeVisible({ timeout: 45_000 });
  });
}
