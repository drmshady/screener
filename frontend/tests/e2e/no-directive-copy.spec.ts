import { test, expect } from '@playwright/test';

const ROUTES = [
  '/',
  '/screen/midterm_52w_high_momentum',
  '/analyze',
  '/candidate/HFRO',
  '/watchlist',
  '/portfolio',
  '/settings',
  '/help',
];

for (const route of ROUTES) {
  test(`no directive trading language found on ${route}`, async ({ page }) => {
    await page.goto(route);
    await expect(page.getByRole('navigation', { name: 'Primary' })).toBeVisible();

    const bodyText = await page.evaluate(() => document.body.innerText);
    const forbiddenWords = [' Buy', ' Sell', 'Recommended', 'Strong buy'];

    for (const word of forbiddenWords) {
      expect(bodyText.toLowerCase()).not.toContain(word.toLowerCase());
    }
  });
}
