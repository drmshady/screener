import { test, expect, Page } from '@playwright/test';
import { isolatePortfolioState } from './_state';

// Feature 016 (US1 / T016): the reworked cockpit home. Confirms the ready-and-fit
// list renders fit-ordered with per-item sizing + heat, a cumulative-heat marker,
// and a sector-clustering note — plus the no-directive lint and the global
// data_as_of / disclaimer envelope on the new home. Also exercises the graceful
// 404 fallback when the pipeline board is unavailable.

const FORBIDDEN_WORDS = [' Buy', ' Sell', 'Recommended', 'Strong buy'];

async function assertNoDirectiveCopy(page: Page) {
  const bodyText = await page.evaluate(() => {
    const clone = document.body.cloneNode(true) as HTMLElement;
    clone.querySelectorAll('[data-personal-use-prompt]').forEach((el) => el.remove());
    return clone.innerText;
  });
  for (const word of FORBIDDEN_WORDS) {
    expect(bodyText.toLowerCase()).not.toContain(word.toLowerCase());
  }
}

const SETTINGS = {
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

function watch(ticker: string, sector: string) {
  return {
    id: `midterm_52w_high_momentum-${ticker}`,
    ticker,
    name: `${ticker} Co`,
    sector,
    strategy_slug: 'midterm_52w_high_momentum',
    saved_at: '2026-06-10T00:00:00Z',
    state: 'saved',
    levels_snapshot: { entry: '100.00', stop_loss: '92.00', take_profit: '118.00' },
  };
}

function seedStorage(page: Page) {
  return page.addInitScript(
    (value) => {
      localStorage.setItem('screener-storage', JSON.stringify(value));
    },
    {
      state: {
        portfolio: {
          schema_version: 3,
          total_capital: 100000,
          holdings: [],
          created_at: '2026-06-11T00:00:00Z',
          updated_at: '2026-06-11T00:00:00Z',
          local_storage_notice_acknowledged: true,
        },
        watchlist: [watch('NVDA', 'Technology'), watch('AMD', 'Technology'), watch('SKIP', 'Unclassified')],
        settings: SETTINGS,
        transactions: [],
        sheet_id: null,
        sheet_range: null,
      },
      version: 6,
    },
  );
}

function sizing(shares: number, heatAfter: number, binding: string) {
  return {
    suggested_shares: shares,
    suggested_position_value: (shares * 100).toFixed(2),
    resulting_position_pct_of_capital: 0.05,
    resulting_sector_pct_of_capital: 0.05,
    caps_respected: true,
    reasoning: `Risk-per-trade target. Binding constraint: ${binding.replace(/_/g, ' ')}.`,
    binding_constraint: binding,
    conviction_used: false,
    conservative_fallback: false,
    reward_to_risk: 2.4,
    portfolio_heat_after_pct: heatAfter,
    data_as_of: '2026-07-03T00:00:00Z',
    disclaimer: 'Fixture disclaimer',
  };
}

function facts(overrides: Record<string, boolean> = {}) {
  return {
    entry_ready: true,
    meaningful_size_survives: true,
    heat_headroom_ok: true,
    sector_room_ok: true,
    not_overconcentrated: true,
    regime_allows_entries: true,
    reward_to_risk_ok: true,
    cash_sufficient: true,
    ...overrides,
  };
}

const BOARD = {
  items: [
    {
      ticker: 'NVDA',
      entry_timing_state: 'entry_ready',
      sizing_preview: sizing(100, 0.05, 'risk_target'),
      fit: {
        score: 100,
        fit_band: 'strong_fit',
        facts: facts(),
        failed_facts: [],
        rationale:
          'Entry-ready and a meaningful position fits within the heat, sector, concentration, and cash limits.',
      },
      sector: 'Technology',
      skipped_reason: null,
    },
    {
      ticker: 'AMD',
      entry_timing_state: 'entry_ready',
      sizing_preview: sizing(80, 0.07, 'risk_target'),
      fit: {
        score: 100,
        fit_band: 'strong_fit',
        facts: facts(),
        failed_facts: [],
        rationale:
          'Entry-ready and a meaningful position fits within the heat, sector, concentration, and cash limits.',
      },
      sector: 'Technology',
      skipped_reason: null,
    },
    {
      ticker: 'SKIP',
      entry_timing_state: null,
      sizing_preview: null,
      fit: null,
      sector: 'Unclassified',
      skipped_reason: 'Ticker not found in current universe snapshot',
    },
  ],
  regime: { regime: 'Trending up' },
  regime_allows_new_entries: true,
  heat_ceiling_pct: 0.06,
  heat_headroom_pct: 0.02,
  available_cash: null,
  personal_use_directive: false,
  data_as_of: '2026-07-03T00:00:00Z',
  disclaimer: 'Fixture disclaimer',
};

test('cockpit home shows the fit-ranked ready list with sizing, heat, and clustering', async ({ page }) => {
  await isolatePortfolioState(page);
  await seedStorage(page);
  await page.route('**/pipeline/board', async (route) => {
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify(BOARD) });
  });

  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Momentum Cockpit' })).toBeVisible();

  const list = page.getByTestId('ready-fit-list');
  await expect(list).toBeVisible();

  // Fit-ordered rows: NVDA and AMD before the skipped one.
  const rows = page.getByTestId('fit-row');
  await expect(rows).toHaveCount(3);
  await expect(rows.nth(0)).toContainText('NVDA');
  await expect(rows.nth(1)).toContainText('AMD');
  await expect(rows.nth(2)).toContainText('SKIP');

  // Per-item sizing + fit band.
  await expect(page.getByTestId('fit-band').first()).toHaveText('Strong fit');
  await expect(rows.nth(0)).toContainText('100 sh');

  // Heat gauge + cumulative-heat marker (AMD pushes cumulative heat past the ceiling).
  await expect(page.getByTestId('heat-gauge')).toBeVisible();
  await expect(page.getByTestId('cumulative-heat-marker')).toBeVisible();

  // Sector clustering note (NVDA + AMD both Technology).
  await expect(page.getByTestId('sector-cluster-note')).toContainText('Technology');

  // Envelope: board data_as_of surfaced + global disclaimer present.
  await expect(page.getByText('Board as of 2026-07-03T00:00:00Z')).toBeVisible();
  await expect(page.getByText(/informational purposes only/i)).toBeVisible();

  await assertNoDirectiveCopy(page);
});

test('cockpit home degrades gracefully to momentum-only links when the board 404s', async ({ page }) => {
  await isolatePortfolioState(page);
  await seedStorage(page);
  await page.route('**/pipeline/board', async (route) => {
    await route.fulfill({ status: 404, contentType: 'application/json', body: JSON.stringify({ detail: 'off' }) });
  });

  await page.goto('/');
  await expect(page.getByTestId('cockpit-fallback')).toBeVisible();
  await expect(page.getByRole('link', { name: /Mid-Term 52-Week High Momentum/ })).toBeVisible();
  // Momentum-only: no value/short-term entry points on the home (FR-012).
  await expect(page.getByText('Mid-Term Value Composite')).toHaveCount(0);
  await expect(page.getByText('Short-Term Minervini VCP')).toHaveCount(0);

  await assertNoDirectiveCopy(page);
});
