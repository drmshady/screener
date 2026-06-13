import { expect, request as requestFactory, test } from '@playwright/test';

const DEFAULT_SETTINGS = {
  per_position_cap_pct: 0.1,
  per_sector_cap_pct: 0.25,
  shariah_filter_on: false,
  shariah_external_sources: ['spus_holdings'],
  shariah_user_inclusion: [],
  shariah_user_exclusion: [],
  liquidity_min_avg_dollar_volume_20d: 1_000_000,
  liquidity_min_price: 5,
  exclude_earnings_within_days_overrides: {},
  default_strategy_slug: 'midterm_52w_high_momentum',
};

type PickedCandidate = {
  ticker: string;
  sector: string;
};

function portfolioState(
  portfolio: Record<string, unknown>,
  settings: Record<string, unknown> = {},
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
        ...DEFAULT_SETTINGS,
        ...settings,
      },
    },
    version: 3,
  };
}

async function pickCandidate(): Promise<PickedCandidate> {
  const request = await requestFactory.newContext({ baseURL: 'http://127.0.0.1:8100' });
  try {
    for (const strategy of ['shortterm_atr_breakout', 'midterm_52w_high_momentum', 'shortterm_minervini_vcp']) {
      const run = await request.post(`/strategies/${strategy}/run`, {
        data: {
          parameters: { regime_gate: false },
          filters: { exclude_earnings_within_days: 0 },
        },
      });
      expect(run.ok()).toBeTruthy();
      const result = await run.json();
      const candidate = result.candidates?.[0] as PickedCandidate | undefined;
      if (candidate) {
        return { ticker: candidate.ticker, sector: candidate.sector };
      }
    }
  } finally {
    await request.dispose();
  }
  throw new Error('No candidate available for sizing test');
}

test('portfolio covers empty state, holdings CRUD, exposure math, concentration flags, and liquidity tags', async ({ page }) => {
  await page.goto('/portfolio');
  await expect(page.getByText('No holdings added yet.')).toBeVisible();

  await page.getByLabel('Total capital').fill('10000');
  await page.getByLabel('Holding ticker').fill('MSFT');
  await page.getByLabel('Shares').fill('30');
  await page.getByLabel('Average cost').fill('90');
  await page.getByLabel('Current price').fill('100');
  await page.getByLabel('Sector').selectOption('Information Technology');
  await page.getByLabel('20-day dollar volume').fill('2000000');
  await page.getByRole('button', { name: 'Add holding' }).click();
  await expect(page.getByRole('dialog')).toContainText('Holdings are stored locally on this device');
  await page.getByRole('button', { name: 'I understand' }).click();

  await page.getByLabel('Holding ticker').fill('LLY');
  await page.getByLabel('Shares').fill('1');
  await page.getByLabel('Average cost').fill('800');
  await page.getByLabel('Current price').fill('900');
  await page.getByLabel('Sector').selectOption('Health Care');
  await page.getByLabel('20-day dollar volume').fill('2000000');
  await page.getByRole('button', { name: 'Add holding' }).click();

  await page.getByLabel('Holding ticker').fill('ABC');
  await page.getByLabel('Shares').fill('2');
  await page.getByLabel('Average cost').fill('4');
  await page.getByLabel('Current price').fill('4');
  await page.getByLabel('Sector').selectOption('Industrials');
  await page.getByLabel('20-day dollar volume').fill('500000');
  await page.getByRole('button', { name: 'Add holding' }).click();

  await expect(page.getByText('$3,908.00')).toBeVisible();
  await expect(page.getByText('$6,092.00')).toBeVisible();
  await expect(page.getByText('$3,000.00 - 30.0%')).toBeVisible();
  await expect(page.getByText('MSFT position is 30.0%, above 10.0%.')).toBeVisible();
  await expect(page.getByText('Information Technology exposure is 30.0%, above 25.0%.')).toBeVisible();
  await expect(page.getByText('Excluded by liquidity gate')).toBeVisible();

  await page.locator('tr', { hasText: 'ABC' }).getByRole('button', { name: 'Edit' }).click();
  await page.getByLabel('Shares').fill('3');
  await page.getByRole('button', { name: 'Save holding' }).click();
  await expect(page.getByText('$3,912.00')).toBeVisible();

  await page.locator('tr', { hasText: 'LLY' }).getByRole('button', { name: 'Remove' }).click();
  await expect(page.locator('tr', { hasText: 'LLY' })).toHaveCount(0);
});

test('settings cap changes propagate immediately to portfolio flags', async ({ page }) => {
  const storage = portfolioState({
    total_capital: 10000,
    holdings: [
      {
        ticker: 'MSFT',
        shares: 30,
        avg_cost: 90,
        current_price: 100,
        sector: 'Information Technology',
        avg_dollar_volume_20d: 2000000,
        added_at: '2026-06-11T00:00:00Z',
      },
    ],
  });

  await page.addInitScript((value) => {
    if (!localStorage.getItem('screener-storage')) {
      localStorage.setItem('screener-storage', JSON.stringify(value));
    }
  }, storage);

  await page.goto('/portfolio');
  await expect(page.getByText('MSFT position is 30.0%, above 10.0%.')).toBeVisible();

  await page.goto('/settings');
  await page.getByLabel('Per-position cap').fill('40');
  await page.getByLabel('Per-sector cap').fill('40');
  await page.waitForFunction(() => {
    const raw = localStorage.getItem('screener-storage');
    if (!raw) {
      return false;
    }
    const parsed = JSON.parse(raw);
    return (
      parsed.state.settings.per_position_cap_pct === 0.4 &&
      parsed.state.settings.per_sector_cap_pct === 0.4
    );
  });

  await page.goto('/portfolio');
  await expect(page.getByText('No cap flags.')).toBeVisible();
});

test('candidate sizing renders a cap-respecting response', async ({ page }) => {
  const candidate = await pickCandidate();
  const successStorage = portfolioState({ total_capital: 100000, holdings: [] });

  await page.addInitScript((value) => {
    localStorage.setItem('screener-storage', JSON.stringify(value));
  }, successStorage);

  await page.goto(`/candidate/${candidate.ticker}`);
  await page.getByRole('button', { name: 'Size this trade' }).first().click();
  await expect(page.getByText('Suggested shares')).toBeVisible({ timeout: 45_000 });
  await expect(page.getByText('Caps respected').locator('xpath=..').getByText('Yes')).toBeVisible();
});

test('candidate sizing renders a cap-breach response', async ({ page }) => {
  const candidate = await pickCandidate();
  const blockedStorage = portfolioState({
    total_capital: 5000,
    holdings: [
      {
        ticker: 'HOLD',
        shares: 12.5,
        avg_cost: 100,
        current_price: 100,
        sector: candidate.sector,
        avg_dollar_volume_20d: 2000000,
        added_at: '2026-06-11T00:00:00Z',
      },
    ],
  });

  await page.addInitScript((value) => {
    localStorage.setItem('screener-storage', JSON.stringify(value));
  }, blockedStorage);

  await page.goto(`/candidate/${candidate.ticker}`);
  await page.getByRole('button', { name: 'Size this trade' }).first().click();
  await expect(page.getByText('Cannot size without breaching cap')).toBeVisible({ timeout: 45_000 });
  await expect(page.getByText('Caps respected').locator('xpath=..').getByText('No')).toBeVisible();
});
