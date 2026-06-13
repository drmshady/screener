import type { Page } from '@playwright/test';

/**
 * Isolate each test from the server-side portfolio blob.
 *
 * `PortfolioSync` hydrates the local store from `GET /portfolio/state` on mount
 * and would otherwise clobber the test's `localStorage` seed with leftover state
 * from a prior test (the backend persists a single shared `portfolio_state.json`).
 * Returning an empty state makes `PortfolioSync` keep the local seed (it seeds the
 * server from local when the server has nothing); the debounced PUT is accepted
 * and not persisted. Register this BEFORE the first `page.goto` in a test.
 */
export async function isolatePortfolioState(page: Page): Promise<void> {
  await page.route('**/portfolio/state', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ state: null, updated_at: null }),
    });
  });
}
