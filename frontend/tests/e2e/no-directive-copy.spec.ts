import { test, expect, Page } from '@playwright/test';
import { isolatePortfolioState } from './_state';

const ROUTES = [
  '/',
  '/screen/midterm_52w_high_momentum',
  '/screen/midterm_value_composite',
  '/analyze',
  '/sentiment',
  '/candidate/HFRO',
  '/watchlist',
  '/portfolio',
  '/settings',
  '/help',
];

const FORBIDDEN_WORDS = [' Buy', ' Sell', 'Recommended', 'Strong buy'];

// Feature 017 (T025 / FR-006 / SC-005): the embedded sentiment & narrative block
// that all three exports (screen / portfolio / watchlist) render. Mirrors the
// backend `_sentiment_section` renderer's app-authored framing — it MUST stay
// directive-free just like app chrome. Embedded into each export's mocked prompt
// below so the rendered preview exercises this copy.
const SENTIMENT_SECTION =
  '\n### External context — sentiment & narrative (informational; does NOT change gates/levels)\n' +
  '- Sentiment label: POSITIVE — Lexicon score +1.00 from 2 positive and 0 negative term hits.\n' +
  '- Narrative (template): NVDA recent sourced context describes stronger demand and a raised outlook.\n' +
  '- Narrative risk: 30/100 (Contained) — signals: earnings beat; raised guidance\n' +
  '- Sources (news present; filing_8k, earnings, analyst_opinion, social omitted):\n' +
  '  - Fixture News, 2026-07-01 — NVDA raises guidance after strong demand';

// Feature 004 / FR-014: the advisor-prompt preview is the ONE place that may
// carry directive framing, and only in personal-use mode where it is marked
// with `data-personal-use-prompt`. Exclude exactly that element from the lint.
// Feature 016 (US4): the in-app transaction-record controls (`data-transaction-
// record`) label the owner's OWN recorded buy/sell trades — factual bookkeeping,
// not directive advice ("Buy"/"Sell" here describe what already happened). Exclude
// those too; the rest of the page (all app chrome) must stay directive-free.
async function assertNoDirectiveCopy(page: Page) {
  const bodyText = await page.evaluate(() => {
    const clone = document.body.cloneNode(true) as HTMLElement;
    clone
      .querySelectorAll('[data-personal-use-prompt], [data-transaction-record]')
      .forEach((el) => el.remove());
    return clone.innerText;
  });
  for (const word of FORBIDDEN_WORDS) {
    expect(bodyText.toLowerCase()).not.toContain(word.toLowerCase());
  }
}

for (const route of ROUTES) {
  test(`no directive trading language found on ${route}`, async ({ page }) => {
    await page.goto(route);
    await expect(page.getByRole('navigation', { name: 'Primary' })).toBeVisible();
    await assertNoDirectiveCopy(page);
  });
}

// ---------------------------------------------------------------------------
// Feature 013 (T036): the import, holdings (sizing / breach-target), and
// watchlist entry-readiness surfaces only render with data, so the route sweep
// above never exercises their dynamic copy. Seed the store + stub the proxy so
// each new surface renders its directive-sensitive states, then lint them too.
// ---------------------------------------------------------------------------

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

function seedStorage(page: Page, state: Record<string, unknown>) {
  return page.addInitScript((value) => {
    localStorage.setItem('screener-storage', JSON.stringify(value));
  }, { state, version: 6 });
}

function levelBlock(status: 'stop_breached' | 'target_reached') {
  return {
    entry: '100.00',
    stop_loss: '92.00',
    tighter_stop_loss: null,
    take_profit: '118.00',
    risk_distance: '8.00',
    reward_distance: '18.00',
    reward_ceiling_basis: 'volatility',
    bounds_applied: [],
    levels_state: 'ok',
    rationale: 'Bounded by volatility over the holding horizon.',
    distance_to_stop_pct: 0.05,
    distance_to_target_pct: 0.18,
    status,
  };
}

test('no directive trading language on the imported-holdings sizing & breach/target surface', async ({ page }) => {
  await isolatePortfolioState(page);
  await seedStorage(page, {
    portfolio: {
      schema_version: 3,
      total_capital: 100000,
      holdings: [],
      created_at: '2026-06-11T00:00:00Z',
      updated_at: '2026-06-11T00:00:00Z',
      local_storage_notice_acknowledged: true,
    },
    watchlist: [],
    settings: SETTINGS,
    transactions: [
      {
        id: 'tx-1',
        ticker: 'TESTCO',
        action: 'buy',
        quantity: '10',
        price: '100.00',
        trade_date: '2025-01-15',
        fees: '1.00',
        note: null,
        source_row: 2,
      },
    ],
    sheet_id: 'sheet-abc',
    sheet_range: 'Transactions!A1:I',
  });

  await page.route('**/portfolio/holdings', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        holdings: [
          {
            ticker: 'TESTCO',
            net_quantity: '10',
            avg_cost: '100.00',
            cost_basis: '1000.00',
            earliest_buy_date: '2025-01-15',
            most_recent_buy_date: '2025-01-15',
            realized_pl: '0.00',
            status: 'open',
            priceable: true,
            sector: 'Technology',
            current_price: '110.00',
            unrealized_pl: '100.00',
            unrealized_pl_pct: 0.1,
            data_notes: [],
            data_as_of: '2026-06-11T21:00:00Z',
            levels: {
              original_plan: levelBlock('stop_breached'),
              current_condition: levelBlock('target_reached'),
            },
            risk: {
              recommended_shares: 8,
              recommended_value: '880.00',
              actual_shares: '10',
              actual_value: '1100.00',
              actual_capital_at_risk: '180.00',
              actual_capital_at_risk_pct: 0.0018,
              per_trade_risk_budget: '150.00',
              over_risk: true,
              binding_constraint: 'per_trade_budget',
              sizing_reasoning: 'Bounded by the per-trade risk budget.',
              fail_open: true,
            },
          },
        ],
        totals: {
          total_invested: '1100.00',
          total_capital_at_risk: '180.00',
          total_capital_at_risk_pct: 0.0018,
        },
        data_as_of: '2026-06-11T21:00:00Z',
        disclaimer: 'Fixture disclaimer',
      }),
    });
  });

  await page.goto('/portfolio');
  await expect(page.getByText('Imported Holdings')).toBeVisible();
  // Confirm the directive-sensitive dynamic copy actually rendered before linting.
  await expect(page.getByText('Stop breached')).toBeVisible();
  await expect(page.getByText('Target reached')).toBeVisible();
  await expect(page.getByText(/Over risk:/)).toBeVisible();

  await assertNoDirectiveCopy(page);
});

test('no directive trading language in the held-position advisor-prompt preview', async ({ page }) => {
  await isolatePortfolioState(page);
  await seedStorage(page, {
    portfolio: {
      schema_version: 3,
      total_capital: 100000,
      holdings: [],
      created_at: '2026-06-11T00:00:00Z',
      updated_at: '2026-06-11T00:00:00Z',
      local_storage_notice_acknowledged: true,
    },
    watchlist: [],
    settings: SETTINGS,
    transactions: [
      {
        id: 'tx-1',
        ticker: 'TESTCO',
        action: 'buy',
        quantity: '10',
        price: '100.00',
        trade_date: '2025-01-15',
        fees: '1.00',
        note: null,
        source_row: 2,
      },
    ],
    sheet_id: 'sheet-abc',
    sheet_range: 'Transactions!A1:I',
  });

  await page.route('**/portfolio/holdings', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        holdings: [
          {
            ticker: 'TESTCO',
            net_quantity: '10',
            avg_cost: '100.00',
            cost_basis: '1000.00',
            earliest_buy_date: '2025-01-15',
            most_recent_buy_date: '2025-01-15',
            realized_pl: '0.00',
            status: 'open',
            priceable: true,
            sector: 'Technology',
            current_price: '110.00',
            unrealized_pl: '100.00',
            unrealized_pl_pct: 0.1,
            data_notes: [],
            data_as_of: '2026-06-11T21:00:00Z',
            levels: {
              original_plan: levelBlock('target_reached'),
              current_condition: levelBlock('target_reached'),
            },
            risk: {
              recommended_shares: 8,
              recommended_value: '880.00',
              actual_shares: '10',
              actual_value: '1100.00',
              actual_capital_at_risk: '180.00',
              actual_capital_at_risk_pct: 0.0018,
              per_trade_risk_budget: '150.00',
              over_risk: true,
              binding_constraint: 'per_trade_budget',
              sizing_reasoning: 'Bounded by the per-trade risk budget.',
              fail_open: false,
            },
          },
        ],
        totals: {
          total_invested: '1100.00',
          total_capital_at_risk: '180.00',
          total_capital_at_risk_pct: 0.0018,
        },
        data_as_of: '2026-06-11T21:00:00Z',
        disclaimer: 'Fixture disclaimer',
      }),
    });
  });

  // Non-directive prompt — the preview is NOT exempt from the lint, so its copy
  // must stay directive-free just like app chrome.
  await page.route('**/portfolio/holdings/advisor-prompt', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        strategy: 'midterm_52w_high_momentum',
        holding_count: 1,
        personal_use_directive: false,
        prompt:
          'TASK: review the positions the user ALREADY HOLDS.\n\n## Held position — TESTCO (Technology)\n- Suggested size: 8 shares vs actual 10 shares\n- Capital at risk: 180.00\n' +
          SENTIMENT_SECTION +
          '\n\n## Honesty & limitations\n- Fixture disclaimer',
        data_as_of: '2026-06-11T21:00:00Z',
        disclaimer: 'Fixture disclaimer',
      }),
    });
  });

  await page.goto('/portfolio');
  await expect(page.getByText('Imported Holdings')).toBeVisible();
  await page.getByRole('button', { name: 'Copy portfolio prompt' }).click();
  await expect(page.getByTestId('holding-advisor-prompt-preview')).toBeVisible();

  await assertNoDirectiveCopy(page);
});

function analyzeBody(ticker: string, ready: boolean) {
  return {
    ticker,
    name: `${ticker} Co`,
    sector: 'Technology',
    strategy: 'midterm_52w_high_momentum',
    as_of: '2026-06-11',
    would_be_selected: ready,
    current_price: '100.00',
    entry: '100.00',
    stop_loss: '92.00',
    tighter_stop_loss: null,
    take_profit: '118.00',
    gate_results: [],
    entry_timing: ready
      ? {
          state: 'entry_ready',
          components: [
            { name: 'trend', status: 'pass', value: 1, reason: 'Above the 200-day average.' },
            { name: 'pivot_proximity', status: 'pass', value: 0.01, reason: 'Near the pivot.' },
          ],
          disqualifiers: [],
          diagnostics: {},
          summary: 'All entry-timing checks are currently met.',
        }
      : {
          state: 'not_entry_ready',
          components: [
            { name: 'pivot_proximity', status: 'fail', value: 0.2, reason: 'Price is far below the pivot.' },
            { name: 'base_maturity', status: 'fail', value: 2, reason: 'Base is too young.' },
          ],
          disqualifiers: [],
          diagnostics: {},
          summary: 'Two entry-timing checks are not yet met.',
        },
    data_as_of: '2026-06-11',
    disclaimer: 'Fixture disclaimer',
  };
}

test('no directive trading language on the watchlist entry-readiness surface', async ({ page }) => {
  await isolatePortfolioState(page);
  await seedStorage(page, {
    portfolio: {
      schema_version: 3,
      total_capital: 100000,
      holdings: [],
      created_at: '2026-06-11T00:00:00Z',
      updated_at: '2026-06-11T00:00:00Z',
      local_storage_notice_acknowledged: true,
    },
    watchlist: [
      {
        id: 'midterm_52w_high_momentum-READY',
        ticker: 'READY',
        name: 'Ready Co',
        sector: 'Technology',
        strategy_slug: 'midterm_52w_high_momentum',
        saved_at: '2026-06-10T00:00:00Z',
        state: 'saved',
        levels_snapshot: { entry: '100.00', stop_loss: '92.00', take_profit: '118.00' },
        last_entry_state: 'not_entry_ready',
      },
      {
        id: 'midterm_52w_high_momentum-WAIT',
        ticker: 'WAIT',
        name: 'Wait Co',
        sector: 'Industrials',
        strategy_slug: 'midterm_52w_high_momentum',
        saved_at: '2026-06-10T00:00:00Z',
        state: 'saved',
        levels_snapshot: { entry: '50.00', stop_loss: '46.00', take_profit: '59.00' },
      },
    ],
    settings: SETTINGS,
    transactions: [],
    sheet_id: null,
    sheet_range: null,
  });

  await page.route('**/analyze/READY**', async (route) => {
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify(analyzeBody('READY', true)) });
  });
  await page.route('**/analyze/WAIT**', async (route) => {
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify(analyzeBody('WAIT', false)) });
  });

  await page.goto('/watchlist');
  // Confirm both entry-readiness states + the "newly ready" flag rendered.
  await expect(page.getByText('Entry ready')).toBeVisible();
  await expect(page.getByText('Watching — not yet ready')).toBeVisible();
  await expect(page.getByText('Newly ready')).toBeVisible();

  await assertNoDirectiveCopy(page);
});

test('sentiment report renders identical sourced copy for the same selection', async ({ page }) => {
  let requestCount = 0;
  await page.route('**/sentiment/report', async (route) => {
    const body = route.request().postDataJSON() as { selections: { ticker: string }[] };
    expect(body.selections.map((selection) => selection.ticker)).toEqual(['NVDA']);
    requestCount += 1;
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        reports: [
          {
            ticker: 'NVDA',
            origin: 'screener',
            label: 'positive',
            label_basis: 'Fixture score from sourced headlines.',
            sentiment_composite: 0.42,
            narrative_risk: {
              score: 18,
              label: 'Low narrative activity',
              signals: ['theme_repetition:low'],
            },
            narrative: 'NVDA recent sourced context: Fixture News on 2026-07-01: Guidance raised after strong demand.',
            narrative_source: 'template',
            budget_state: 'ok',
            source_classes_present: ['news'],
            source_classes_omitted: ['filing_8k', 'earnings', 'analyst_opinion', 'social'],
            sources: [
              {
                id: 'fixture:nvda:1',
                source_class: 'news',
                title: 'Guidance raised after strong demand',
                publisher: 'Fixture News',
                published_at: '2026-07-01T12:00:00Z',
                reference_url: 'https://example.test/nvda',
                is_stale: false,
                score: 0.42,
              },
            ],
            fingerprint: 'sha256:fixture',
            resolution: null,
          },
        ],
        period_spend_usd: '0',
        monthly_cap_usd: '5.00',
        data_as_of: '2026-07-02T21:00:00Z',
        disclaimer: 'Fixture disclaimer',
      }),
    });
  });

  await page.goto('/sentiment?ticker=NVDA&origin=screener');
  await page.getByRole('button', { name: 'Run report' }).click();
  await expect(page.getByText('NVDA recent sourced context')).toBeVisible();
  const firstRender = await page.locator('article').innerText();
  await assertNoDirectiveCopy(page);

  await page.getByRole('button', { name: 'Run report' }).click();
  await expect(page.locator('article')).toHaveCount(1);
  expect(await page.locator('article').innerText()).toBe(firstRender);
  expect(requestCount).toBe(2);
});

// ---------------------------------------------------------------------------
// Feature 017 (T025 / FR-006 / SC-005): the rendered `prompt` preview of ALL
// THREE exports must stay directive-free, including the embedded sentiment &
// narrative section. The portfolio (US2) export preview above already embeds
// SENTIMENT_SECTION; these two cover the screen (US1) and watchlist (US3)
// export previews.
// ---------------------------------------------------------------------------

function screenCandidate(ticker: string) {
  return {
    ticker,
    name: `${ticker} Inc`,
    sector: 'Technology',
    strategy_slug: 'midterm_52w_high_momentum',
    current_price: '100.00',
    entry: '100.00',
    stop_loss: '90.00',
    tighter_stop_loss: '95.00',
    take_profit: '130.00',
    rank: 1,
    score: 0.5,
    reason: 'matched',
    return_12_1: 0.4,
    gate_results: [{ gate: '52-week-high proximity', status: 'pass', detail: '1% below high' }],
    recent_8k_count_30d: 0,
  };
}

test('no directive trading language in the screener-results advisor-prompt preview', async ({ page }) => {
  await isolatePortfolioState(page);

  await page.route('**/strategies/midterm_52w_high_momentum/run', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        id: 'screen-1',
        strategy_slug: 'midterm_52w_high_momentum',
        as_of_date: '2026-06-12',
        parameters_snapshot: {},
        filters_snapshot: {},
        candidate_count: 1,
        candidates: [screenCandidate('NVDA')],
        computed_at: '2026-06-12T00:00:00Z',
        data_as_of: '2026-06-12T21:00:00Z',
        disclaimer: 'Fixture disclaimer',
        regime: 'Trending up',
      }),
    });
  });

  // Non-directive prompt WITH the embedded sentiment section — the preview is NOT
  // exempt from the lint.
  await page.route('**/strategies/midterm_52w_high_momentum/advisor-prompt', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        strategy: 'midterm_52w_high_momentum',
        candidate_count: 1,
        personal_use_directive: false,
        prompt:
          '## Strategy — Mid-Term 52-Week High Momentum\n\n### #1 NVDA — NVDA Inc (Technology)\n- Entry 100.00 | Stop 90.00 | Target 130.00\n' +
          SENTIMENT_SECTION +
          '\n\n## Honesty & limitations\n- Fixture disclaimer',
        data_as_of: '2026-06-12T21:00:00Z',
        disclaimer: 'Fixture disclaimer',
      }),
    });
  });

  await page.goto('/screen/midterm_52w_high_momentum');
  await page.getByRole('button', { name: 'Run Screen' }).click();

  const copyButton = page.getByRole('button', { name: 'Copy advisor prompt (all results)' });
  await expect(copyButton).toBeVisible();
  await copyButton.click();

  const preview = page.getByTestId('screen-advisor-prompt-preview');
  await page
    .locator('details:has([data-testid="screen-advisor-prompt-preview"]) summary')
    .click();
  await expect(preview).toBeVisible();
  await expect(preview).toContainText('External context');

  await assertNoDirectiveCopy(page);
});

test('no directive trading language in the watchlist advisor-prompt preview', async ({ page }) => {
  await isolatePortfolioState(page);
  await seedStorage(page, {
    portfolio: {
      schema_version: 3,
      total_capital: 100000,
      holdings: [],
      created_at: '2026-06-11T00:00:00Z',
      updated_at: '2026-06-11T00:00:00Z',
      local_storage_notice_acknowledged: true,
    },
    watchlist: [
      {
        id: 'midterm_52w_high_momentum-NVDA',
        ticker: 'NVDA',
        name: 'NVDA Inc',
        sector: 'Technology',
        strategy_slug: 'midterm_52w_high_momentum',
        saved_at: '2026-06-10T00:00:00Z',
        state: 'saved',
        levels_snapshot: { entry: '100.00', stop_loss: '90.00', take_profit: '130.00' },
      },
    ],
    settings: SETTINGS,
    transactions: [],
    sheet_id: null,
    sheet_range: null,
  });

  await page.route('**/analyze/NVDA**', async (route) => {
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify(analyzeBody('NVDA', true)) });
  });

  await page.route('**/portfolio/watchlist/advisor-prompt', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        strategy: 'midterm_52w_high_momentum',
        watched_count: 1,
        personal_use_directive: false,
        prompt:
          '## Strategy — Mid-Term 52-Week High Momentum\n\n### NVDA — NVDA Inc (Technology)\n- Entry 100.00 | Stop 90.00 | Target 130.00\n' +
          SENTIMENT_SECTION +
          '\n\n## Honesty & limitations\n- Fixture disclaimer',
        data_as_of: '2026-06-12T21:00:00Z',
        disclaimer: 'Fixture disclaimer',
      }),
    });
  });

  await page.goto('/watchlist');
  const copyButton = page.getByRole('button', { name: 'Copy watchlist advisor prompt' });
  await expect(copyButton).toBeVisible();
  await copyButton.click();

  const preview = page.getByTestId('watchlist-advisor-prompt-preview');
  await page
    .locator('details:has([data-testid="watchlist-advisor-prompt-preview"]) summary')
    .click();
  await expect(preview).toBeVisible();
  await expect(preview).toContainText('External context');

  await assertNoDirectiveCopy(page);
});
