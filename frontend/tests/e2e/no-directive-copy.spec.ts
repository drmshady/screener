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

    // Feature 004 / FR-014: the advisor-prompt preview is the ONE place that may
    // carry directive framing, and only in personal-use mode where it is marked
    // with `data-personal-use-prompt`. Exclude exactly that element from the lint;
    // the rest of the page (all app chrome) must stay directive-free.
    const bodyText = await page.evaluate(() => {
      const clone = document.body.cloneNode(true) as HTMLElement;
      clone
        .querySelectorAll('[data-personal-use-prompt]')
        .forEach((el) => el.remove());
      return clone.innerText;
    });
    const forbiddenWords = [' Buy', ' Sell', 'Recommended', 'Strong buy'];

    for (const word of forbiddenWords) {
      expect(bodyText.toLowerCase()).not.toContain(word.toLowerCase());
    }
  });
}
