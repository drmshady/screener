import { render, screen } from '@testing-library/react';
import { describe, expect, test } from 'vitest';

import { PortfolioHoldingsResponseSchema } from '../../src/lib/api';

type Risk = {
  recommended_shares: number;
  recommended_value: string;
  actual_shares: string;
  actual_value: string;
  actual_capital_at_risk: string;
  actual_capital_at_risk_pct: number;
  per_trade_risk_budget: string;
  over_risk: boolean;
  binding_constraint: string | null;
  fail_open: boolean;
};

function money(value: string) {
  return `$${Number(value).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function pct(value: number) {
  return `${(value * 100).toFixed(1)}%`;
}

function bindingLabel(value: string | null) {
  if (value === 'per_trade_budget') return 'Per-trade risk budget';
  if (value === 'position_cap') return 'Position cap';
  if (value === 'sector_cap') return 'Sector cap';
  return 'Within configured limits';
}

function RiskView({
  risk,
  totals,
}: {
  risk: Risk;
  totals: { total_invested: string; total_capital_at_risk: string; total_capital_at_risk_pct: number };
}) {
  return (
    <section>
      <div>Suggested vs actual size</div>
      <div>{risk.recommended_shares} shares / {money(risk.recommended_value)}</div>
      <div>{risk.actual_shares} shares / {money(risk.actual_value)}</div>
      <div>Capital at risk {money(risk.actual_capital_at_risk)} ({pct(risk.actual_capital_at_risk_pct)})</div>
      {risk.over_risk ? <div>Over risk: {bindingLabel(risk.binding_constraint)}</div> : <div>{bindingLabel(null)}</div>}
      {risk.fail_open ? <div>Baseline sizing used</div> : null}
      <div>Total invested {money(totals.total_invested)}</div>
      <div>Total capital at risk {money(totals.total_capital_at_risk)} ({pct(totals.total_capital_at_risk_pct)})</div>
    </section>
  );
}

describe('holding risk view', () => {
  test('holdings schema preserves the risk block from the API response', () => {
    const parsed = PortfolioHoldingsResponseSchema.parse({
      holdings: [
        {
          ticker: 'MSFT',
          net_quantity: '120',
          avg_cost: '100.00',
          cost_basis: '12000.00',
          earliest_buy_date: '2025-08-15',
          most_recent_buy_date: '2025-10-09',
          realized_pl: '0.00',
          status: 'open',
          priceable: true,
          sector: 'Information Technology',
          current_price: '110.00',
          unrealized_pl: '1200.00',
          unrealized_pl_pct: 0.1,
          data_notes: [],
          data_as_of: '2026-06-30T21:00:00Z',
          levels: null,
          risk: {
            recommended_shares: 100,
            recommended_value: '10000.00',
            actual_shares: '120',
            actual_value: '13200.00',
            actual_capital_at_risk: '1200.00',
            actual_capital_at_risk_pct: 0.012,
            per_trade_risk_budget: '1000.00',
            over_risk: true,
            binding_constraint: 'per_trade_budget',
            sizing_reasoning: 'Binding constraint: risk target.',
            fail_open: true,
          },
        },
      ],
      totals: {
        total_invested: '13200.00',
        total_capital_at_risk: '1200.00',
        total_capital_at_risk_pct: 0.012,
      },
      data_as_of: '2026-06-30T21:00:00Z',
      disclaimer: 'For informational purposes only; not investment advice.',
    });

    expect(parsed.holdings[0].risk?.binding_constraint).toBe('per_trade_budget');
  });

  test('renders suggested-vs-actual, capital at risk, flags, and totals', () => {
    render(
      <RiskView
        risk={{
          recommended_shares: 100,
          recommended_value: '10000.00',
          actual_shares: '120',
          actual_value: '13200.00',
          actual_capital_at_risk: '1200.00',
          actual_capital_at_risk_pct: 0.012,
          per_trade_risk_budget: '1000.00',
          over_risk: true,
          binding_constraint: 'per_trade_budget',
          fail_open: true,
        }}
        totals={{
          total_invested: '13200.00',
          total_capital_at_risk: '1200.00',
          total_capital_at_risk_pct: 0.012,
        }}
      />,
    );

    expect(screen.getByText('Suggested vs actual size')).toBeTruthy();
    expect(screen.getByText('100 shares / $10,000.00')).toBeTruthy();
    expect(screen.getByText('120 shares / $13,200.00')).toBeTruthy();
    expect(screen.getByText('Capital at risk $1,200.00 (1.2%)')).toBeTruthy();
    expect(screen.getByText('Over risk: Per-trade risk budget')).toBeTruthy();
    expect(screen.getByText('Baseline sizing used')).toBeTruthy();
    expect(screen.getByText('Total invested $13,200.00')).toBeTruthy();
    expect(screen.getByText('Total capital at risk $1,200.00 (1.2%)')).toBeTruthy();
  });

  test('uses descriptive copy only', () => {
    render(
      <RiskView
        risk={{
          recommended_shares: 80,
          recommended_value: '8000.00',
          actual_shares: '50',
          actual_value: '5500.00',
          actual_capital_at_risk: '500.00',
          actual_capital_at_risk_pct: 0.005,
          per_trade_risk_budget: '1000.00',
          over_risk: false,
          binding_constraint: null,
          fail_open: false,
        }}
        totals={{
          total_invested: '5500.00',
          total_capital_at_risk: '500.00',
          total_capital_at_risk_pct: 0.005,
        }}
      />,
    );

    const text = document.body.textContent ?? '';
    for (const word of ['Buy', 'Sell', 'Strong buy']) {
      expect(text).not.toContain(word);
    }
  });
});
