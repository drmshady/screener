import { expect, test, type BrowserContext } from '@playwright/test';
import { encode } from 'next-auth/jwt';

const hostedAuthConfigured =
  process.env.SCREENER_HOSTED_MODE === '1' &&
  process.env.AUTH_SECRET &&
  process.env.SCREENER_OWNER_EMAIL;

const screenPayload = {
  id: 'hosted-demo',
  strategy_slug: 'midterm_52w_high_momentum',
  as_of_date: '2026-07-06',
  parameters_snapshot: {},
  filters_snapshot: {},
  candidate_count: 1,
  candidates: [
    {
      ticker: 'AAPL',
      name: 'Apple Inc.',
      sector: 'Technology',
      strategy_slug: 'midterm_52w_high_momentum',
      strategy_name: 'Mid-term 52w High Momentum',
      timeframe: 'midterm',
      current_price: '210.00',
      entry: '212.00',
      stop_loss: '196.00',
      tighter_stop_loss: null,
      take_profit: '244.00',
      rank: 1,
      score: 1.23,
      reason: 'Test fixture',
      gate_results: [{ gate: 'Liquidity', status: 'pass', detail: 'ADV ok' }],
      warnings: [],
      data_integrity_warnings: [],
      data_suspect: false,
      recent_8k_count_30d: 0,
      material_input_freshness: {
        prices: '2026-07-06',
        fundamentals: '2026-07-05',
        regime: '2026-07-06',
      },
    },
  ],
  computed_at: '2026-07-06T22:00:00Z',
  data_as_of: '2026-07-06T21:00:00Z',
  disclaimer: 'Informational only.',
  stale_sources: [],
  data_notes: [],
  material_input_freshness: {
    prices: '2026-07-06',
    fundamentals: '2026-07-05',
    regime: '2026-07-06',
  },
  regime: 'Trending up',
  regime_allows_new_entries: true,
  regime_note: null,
};

async function addOwnerSession(context: BrowserContext, baseURL: string) {
  const token = await encode({
    secret: process.env.AUTH_SECRET!,
    token: {
      email: process.env.SCREENER_OWNER_EMAIL!,
      name: 'Owner',
      sub: 'owner',
    },
  });
  await context.addCookies([
    {
      name: 'next-auth.session-token',
      value: token,
      url: baseURL,
      httpOnly: true,
      sameSite: 'Lax',
    },
  ]);
}

test.describe('hosted owner usable flow', () => {
  test.skip(!hostedAuthConfigured, 'requires hosted-mode auth env');

  test('owner can run a momentum screen through the same-origin proxy', async ({ page, context, baseURL }) => {
    await addOwnerSession(context, baseURL!);
    await page.route('**/api/proxy/data/freshness', async (route) => {
      await route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({
          sources: [
            {
              source_name: 'yfinance',
              kind: 'prices',
              data_as_of: '2026-07-06',
              latest_session: '2026-07-06',
              sessions_behind: 0,
              is_stale: false,
              last_refresh_outcome: 'skipped-current',
            },
          ],
          any_stale: false,
          latest_session: '2026-07-06',
          data_as_of: '2026-07-06T21:00:00Z',
          disclaimer: 'Informational only.',
        }),
      });
    });
    await page.route('**/api/proxy/strategies/midterm_52w_high_momentum/run', async (route) => {
      await route.fulfill({ contentType: 'application/json', body: JSON.stringify(screenPayload) });
    });

    await page.goto('/screen/midterm_52w_high_momentum');
    await page.getByRole('button', { name: 'Run Screen' }).click();

    await expect(page.getByText('AAPL')).toBeVisible();
    await expect(page.getByText('212.00')).toBeVisible();
    await expect(page.getByText('Liquidity')).toBeVisible();
    await expect(page.getByText('Data is current for latest completed session 2026-07-06.')).toBeVisible();
    await expect(page.getByText('Informational only.')).toBeVisible();
    await expect(page.getByText(/buy|sell|recommended|strong buy/i)).toHaveCount(0);
  });

  test('owner sees explicit empty state and cold-start loading remains usable', async ({ page, context, baseURL }) => {
    await addOwnerSession(context, baseURL!);
    await page.route('**/api/proxy/data/freshness', async (route) => {
      await route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({
          sources: [],
          any_stale: false,
          latest_session: '2026-07-06',
          data_as_of: '2026-07-06T21:00:00Z',
          disclaimer: 'Informational only.',
        }),
      });
    });
    await page.route('**/api/proxy/strategies/midterm_52w_high_momentum/run', async (route) => {
      await new Promise((resolve) => setTimeout(resolve, 250));
      await route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({ ...screenPayload, candidate_count: 0, candidates: [] }),
      });
    });

    await page.goto('/screen/midterm_52w_high_momentum');
    await page.getByRole('button', { name: 'Run Screen' }).click();

    await expect(page.getByText(/Running screen/)).toBeVisible();
    await expect(page.getByText('No candidates matched the active filters.')).toBeVisible();
  });
});
