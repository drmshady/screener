/**
 * Feature 019 US4 (T021): realized win/loss scoreboard.
 *
 * `RealizedSummary` reads the existing `PortfolioTotals` realized fields
 * (`winning_trade_count`, `closed_trade_count`, `win_rate`, `realized_pnl`) — no
 * new computation — and shows count won, count lost (closed − won), win rate %,
 * and total realized P&L, consistent with the underlying closed trades (SC-004).
 * With no closed positions it renders an explicit "No realized history yet"
 * empty state (FR-009). Every render carries `data_as_of` + the disclaimer
 * (FR-012).
 */

import { render, screen } from '@testing-library/react';
import { describe, expect, test } from 'vitest';

import { RealizedSummary } from '@/components/RealizedSummary';
import type { PortfolioTotals } from '@/lib/api';

function totals(overrides: Partial<PortfolioTotals> = {}): PortfolioTotals {
  return {
    total_invested: '0.00',
    total_capital_at_risk: '0.00',
    total_capital_at_risk_pct: 0,
    heat_ceiling_pct: 0,
    heat_headroom_pct: 0,
    realized_pnl: null,
    unrealized_pnl: null,
    total_pnl: null,
    win_rate: null,
    closed_trade_count: 0,
    winning_trade_count: 0,
    ...overrides,
  } as PortfolioTotals;
}

describe('RealizedSummary (US4)', () => {
  test('renders won/lost counts, win rate %, and total realized P&L', () => {
    render(
      <RealizedSummary
        totals={totals({
          realized_pnl: '1234.50',
          closed_trade_count: 5,
          winning_trade_count: 3,
          win_rate: 0.6,
        })}
        dataAsOf="2026-06-12T00:00:00Z"
        disclaimer="Informational only."
      />,
    );

    expect(screen.getByTestId('realized-summary')).toBeTruthy();
    // 5 closed, 3 won ⇒ 2 lost.
    expect(screen.getByTestId('realized-won').textContent).toContain('3');
    expect(screen.getByTestId('realized-lost').textContent).toContain('2');
    // win_rate 0.6 ⇒ 60%.
    expect(screen.getByTestId('realized-win-rate').textContent).toContain('60');
    // total realized P&L rendered as money (shared formatMoney ⇒ no separators).
    expect(screen.getByTestId('realized-total').textContent).toContain('1234.50');
    // disclosure (FR-012).
    expect(screen.getByTestId('realized-disclaimer').textContent).toContain('Informational only.');
  });

  test('zero-closed renders the explicit empty state (FR-009)', () => {
    render(<RealizedSummary totals={totals()} disclaimer="Informational only." />);

    expect(screen.getByTestId('realized-empty').textContent).toContain('No realized history yet');
    // No scoreboard figures when there is nothing closed.
    expect(screen.queryByTestId('realized-won')).toBeNull();
  });

  test('renders the empty state when totals is absent', () => {
    render(<RealizedSummary totals={null} disclaimer="d" />);
    expect(screen.getByTestId('realized-empty')).toBeTruthy();
  });
});
