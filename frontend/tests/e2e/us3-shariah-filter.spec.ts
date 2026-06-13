import { expect, request as requestFactory, test } from '@playwright/test';
import { isolatePortfolioState } from './_state';

test.beforeEach(async ({ page }) => {
  await isolatePortfolioState(page);
});

const STRATEGIES = [
  'midterm_52w_high_momentum',
  'shortterm_minervini_vcp',
  'shortterm_atr_breakout',
];

type PickedCandidates = {
  strategy: string;
  ticker: string;
};

async function pickCandidate(spusCompliant: boolean): Promise<PickedCandidates> {
  const request = await requestFactory.newContext({ baseURL: 'http://127.0.0.1:8100' });
  try {
    for (const strategy of STRATEGIES) {
      const run = await request.post(`/strategies/${strategy}/run`, {
        data: { filters: { shariah_only: false } },
      });
      expect(run.ok()).toBeTruthy();
      const result = await run.json();
      const candidates = result.candidates as Array<{ ticker: string }>;

      for (const candidate of candidates) {
        const statusResponse = await request.get(`/shariah/status/${candidate.ticker}?sources=spus_holdings`);
        expect(statusResponse.ok()).toBeTruthy();
        const status = await statusResponse.json();
        if (Boolean(status.is_compliant) === spusCompliant) {
          return { strategy, ticker: candidate.ticker };
        }
      }
    }
  } finally {
    await request.dispose();
  }
  throw new Error(`No current candidate matched SPUS compliance=${spusCompliant}`);
}

function persistedState(
  settings: Record<string, unknown>,
  portfolio: Record<string, unknown> = { total_capital: 100000, holdings: [] },
) {
  const timestamp = '2026-06-11T00:00:00Z';
  return {
    state: {
      portfolio: {
        schema_version: 3,
        total_capital: 100000,
        holdings: [],
        created_at: timestamp,
        updated_at: timestamp,
        local_storage_notice_acknowledged: true,
        ...portfolio,
      },
      watchlist: [],
      settings: {
        per_position_cap_pct: 0.1,
        per_sector_cap_pct: 0.25,
        shariah_filter_on: true,
        shariah_external_sources: ['spus_holdings'],
        shariah_user_inclusion: [],
        shariah_user_exclusion: [],
        liquidity_min_avg_dollar_volume_20d: 1000000,
        liquidity_min_price: 5,
        exclude_earnings_within_days_overrides: {},
        default_strategy_slug: 'midterm_52w_high_momentum',
        ...settings,
      },
    },
    version: 4,
  };
}

test('settings exposes Shariah sources and conflict warnings', async ({ page }) => {
  await page.goto('/settings');

  await page.getByLabel('Shariah-compliant only').check();
  await expect(page.getByLabel('SPUS holdings')).toBeChecked();
  await expect(page.getByLabel('Halal Terminal')).toBeVisible();
  await expect(page.getByLabel('Finispia')).toBeVisible();

  await page.getByPlaceholder('Ticker').first().fill('UNH');
  await page.getByPlaceholder('Note').first().fill('Personal review');
  await page.getByRole('button', { name: 'Add include' }).click();

  await page.getByPlaceholder('Ticker').nth(1).fill('UNH');
  await page.getByPlaceholder('Note').nth(1).fill('Personal exclusion');
  await page.getByRole('button', { name: 'Add exclude' }).click();

  await expect(page.getByText('Conflicting overrides: UNH')).toBeVisible();
});

test('Shariah filter applies user inclusion', async ({ page }) => {
  const picked = await pickCandidate(false);
  const storage = persistedState({
    shariah_external_sources: ['spus_holdings'],
    shariah_user_inclusion: [
      {
        ticker: picked.ticker,
        direction: 'include',
        added_at: '2026-06-10T00:00:00Z',
        note: 'Personal review',
      },
    ],
  });

  await page.addInitScript((value) => {
    localStorage.setItem('screener-storage', JSON.stringify(value));
  }, storage);

  await page.goto(`/screen/${picked.strategy}`);
  await page.getByRole('button', { name: 'Run Screen' }).click();

  await expect(page.getByRole('link', { name: picked.ticker })).toBeVisible();
  await expect(page.getByText('Shariah-compliant (User)')).toBeVisible();
});

test('Shariah filter applies user exclusion over external source', async ({ page }) => {
  const picked = await pickCandidate(true);
  const storage = persistedState({
    shariah_user_exclusion: [
      {
        ticker: picked.ticker,
        direction: 'exclude',
        added_at: '2026-06-10T00:00:00Z',
        note: 'Personal exclusion',
      },
    ],
  });

  await page.addInitScript((value) => {
    localStorage.setItem('screener-storage', JSON.stringify(value));
  }, storage);

  await page.goto(`/screen/${picked.strategy}`);
  await page.getByRole('button', { name: 'Run Screen' }).click();

  await expect(page.getByRole('link', { name: picked.ticker })).toHaveCount(0);
});

test('portfolio rows show excluded-by-user badge and summary counts', async ({ page }) => {
  const storage = persistedState(
    {
      shariah_user_exclusion: [
        {
          ticker: 'LLY',
          direction: 'exclude',
          added_at: '2026-06-10T00:00:00Z',
          note: 'Portfolio exclusion',
        },
      ],
    },
    {
      total_capital: 100000,
      holdings: [
        {
          ticker: 'LLY',
          shares: 2,
          avg_cost: 800,
          current_price: 800,
          sector: 'Health Care',
          avg_dollar_volume_20d: 2000000,
          added_at: '2026-06-10T00:00:00Z',
        },
      ],
    },
  );

  await page.addInitScript((value) => {
    localStorage.setItem('screener-storage', JSON.stringify(value));
  }, storage);

  await page.goto('/portfolio');

  await expect(page.getByText('User-marked count')).toBeVisible();
  await expect(page.getByText('Excluded by user')).toBeVisible();
  await expect(page.getByText('Non-compliant count').locator('xpath=..').getByText('1')).toBeVisible();
});
