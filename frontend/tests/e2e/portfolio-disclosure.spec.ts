import { expect, test, Page } from '@playwright/test';
import { isolatePortfolioState } from './_state';

/**
 * Feature 019 (Phase 7 / T024): cross-cutting disclosure + no-directive lint for
 * the Portfolio decision surface. With the single-owner carve-out OFF
 * (`directive_enabled=false`) the position cards and the realized summary must
 * carry NO Hold/Trim/Sell verb — only the neutral status label — and every card
 * plus the summary must carry `data_as_of` + the disclaimer (FR-008 / FR-012).
 *
 * The verb chip (`data-testid="instruction-directive"`) is the ONLY place a
 * directive word renders, so asserting it never appears — even though the mocked
 * payload deliberately carries `directive: "sell"` — precisely proves the gate.
 */

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

// One seeded open buy so `computeImportedHoldings` yields an open NVDA holding,
// which — intersected with the mocked /portfolio/holdings detail — renders a card.
const SEEDED_STATE = {
  state: {
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
        id: 'txn-nvda-1',
        ticker: 'NVDA',
        action: 'buy',
        quantity: '10',
        price: '100.00',
        trade_date: '2025-01-02',
        fees: null,
        note: null,
        source_row: 1,
      },
    ],
    sheet_id: null,
    sheet_range: null,
  },
  version: 3,
};

const DATA_AS_OF = '2026-06-11T21:00:00Z';
const DISCLAIMER = 'Informational only. Not investment advice.';

function okLevel(status: 'holding' | 'stop_breached' | 'target_reached') {
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
    distance_to_stop_pct: 0.08,
    distance_to_target_pct: 0.18,
    status,
  };
}

// Carve-out OFF: `directive_enabled=false`. The payload still carries a
// `directive: "sell"` verb to prove the frontend gate — not the payload — is
// what suppresses it.
function holdingsBody() {
  return {
    holdings: [
      {
        ticker: 'NVDA',
        net_quantity: '10',
        avg_cost: '100.00',
        cost_basis: '1000.00',
        earliest_buy_date: '2025-01-02',
        most_recent_buy_date: '2025-01-02',
        realized_pl: '0.00',
        status: 'open',
        priceable: true,
        sector: 'Technology',
        current_price: '110.00',
        unrealized_pl: '100.00',
        unrealized_pl_pct: 0.1,
        data_notes: [],
        data_as_of: DATA_AS_OF,
        levels: {
          original_plan: okLevel('holding'),
          current_condition: okLevel('holding'),
          trailing: null,
        },
        risk: null,
        instruction: {
          status_label: 'Holding',
          directive: 'sell',
          rationale: 'Price is holding above the stop.',
          inputs: {
            level_status: 'holding',
            distance_to_stop_pct: 0.08,
            heat_headroom_pct: 0.5,
            stage: null,
          },
        },
      },
    ],
    totals: {
      total_invested: '1100.00',
      total_capital_at_risk: '180.00',
      total_capital_at_risk_pct: 0.0018,
      heat_ceiling_pct: 0.06,
      heat_headroom_pct: 0.5,
      realized_pnl: '350.00',
      unrealized_pnl: '100.00',
      total_pnl: '450.00',
      win_rate: 0.5,
      closed_trade_count: 2,
      winning_trade_count: 1,
    },
    realized_trades: [],
    directive_enabled: false,
    data_as_of: DATA_AS_OF,
    disclaimer: DISCLAIMER,
  };
}

async function gotoPortfolio(page: Page) {
  await isolatePortfolioState(page);
  await page.addInitScript((value) => {
    localStorage.setItem('screener-storage', JSON.stringify(value));
  }, SEEDED_STATE);
  await page.route('**/portfolio/holdings', async (route) => {
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify(holdingsBody()) });
  });
  await page.goto('/portfolio');
}

test('carve-out OFF: no directive verb on the position card, only the neutral status', async ({ page }) => {
  await gotoPortfolio(page);

  const card = page.getByTestId('position-card').first();
  await expect(card).toBeVisible();

  // The verb chip is the sole source of a directive word — it must never render
  // when the carve-out is off, even though the payload carries directive:"sell".
  await expect(page.getByTestId('instruction-directive')).toHaveCount(0);
  // The instruction section is never dropped: the neutral status label shows.
  await expect(card.getByTestId('instruction-status')).toHaveText('Holding');
});

test('every position card carries data_as_of + the disclaimer (FR-012)', async ({ page }) => {
  await gotoPortfolio(page);

  const cards = page.getByTestId('position-card');
  const count = await cards.count();
  expect(count).toBeGreaterThan(0);
  for (let i = 0; i < count; i += 1) {
    const card = cards.nth(i);
    await expect(card.getByTestId('card-disclaimer')).toHaveText(DISCLAIMER);
    // AsOfBadge renders the response/holding as-of on the card footer.
    await expect(card.getByText(/as of/i).first()).toBeVisible();
  }
});

test('the realized summary renders its scoreboard with the disclaimer (FR-009/FR-012)', async ({ page }) => {
  await gotoPortfolio(page);

  const summary = page.getByTestId('realized-summary');
  await expect(summary).toBeVisible();
  // 2 closed, 1 won ⇒ 1 lost; win_rate 0.5 ⇒ 50%.
  await expect(summary.getByTestId('realized-won')).toHaveText('1');
  await expect(summary.getByTestId('realized-lost')).toHaveText('1');
  await expect(summary.getByTestId('realized-win-rate')).toContainText('50');
  await expect(summary.getByTestId('realized-disclaimer')).toHaveText(DISCLAIMER);
});
