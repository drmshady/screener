/**
 * Feature 019 (US1): Vitest render + graceful-degradation tests for PositionCard.
 *
 *  - Card shell (levels/status/instruction) renders without waiting on the
 *    lazily-loaded sentiment/news sections (SC-005).
 *  - "Levels unavailable" edge case still renders the card (FR-004).
 *  - Empty news → explicit "nothing new" (FR-005).
 *  - Sentiment section renders (capped/absent degrades to a template, never a
 *    blank/error) — the sentiment child is stubbed here so the shell is testable.
 *  - directive_enabled=false → neutral status label, no Hold/Trim/Sell verb (FR-008).
 *  - directive_enabled=true → the verb renders.
 */

import { render, screen } from '@testing-library/react';
import { expect, test, vi } from 'vitest';

// Stub the lazy sentiment child so the shell is synchronously testable (SC-005).
vi.mock('@/components/SentimentReport', () => ({
  SentimentReport: () => <div data-testid="sentiment-stub">sentiment</div>,
}));

import { PositionCard } from '@/components/PositionCard';
import type { InstructionBlock, PortfolioHoldingWithLevels } from '@/lib/api';

function levelBlock(overrides: Record<string, unknown> = {}) {
  return {
    levels_state: 'ok',
    rationale: 'Bounded levels.',
    status: 'holding',
    stop_loss: '90.00',
    take_profit: '130.00',
    distance_to_stop_pct: -0.15,
    bounds_applied: [],
    ...overrides,
  };
}

function instruction(overrides: Partial<InstructionBlock> = {}): InstructionBlock {
  return {
    status_label: 'Holding',
    directive: 'hold',
    rationale: 'Position within plan; the current-condition stop and target are intact.',
    inputs: { level_status: 'holding', distance_to_stop_pct: -0.15, heat_headroom_pct: 0.5, stage: null },
    ...overrides,
  } as InstructionBlock;
}

function holding(overrides: Record<string, unknown> = {}): PortfolioHoldingWithLevels {
  return {
    ticker: 'NVDA',
    net_quantity: '10',
    avg_cost: '100.00',
    cost_basis: '1000.00',
    earliest_buy_date: '2025-01-02',
    most_recent_buy_date: '2025-01-02',
    realized_pl: '0.00',
    status: 'open',
    priceable: true,
    sector: 'Information Technology',
    current_price: '110.00',
    unrealized_pl: '100.00',
    unrealized_pl_pct: 0.1,
    data_notes: [],
    data_as_of: '2026-06-12T00:00:00Z',
    levels: { original_plan: levelBlock(), current_condition: levelBlock() },
    instruction: instruction(),
    ...overrides,
  } as unknown as PortfolioHoldingWithLevels;
}

test('renders the shell (ticker, levels, status) synchronously', () => {
  render(
    <PositionCard
      holding={holding()}
      directiveEnabled={false}
      dataAsOf="2026-06-12T00:00:00Z"
      disclaimer="Informational only."
    />,
  );
  expect(screen.getByTestId('position-card')).toBeTruthy();
  expect(screen.getByText('NVDA')).toBeTruthy();
  expect(screen.getByText('$90.00')).toBeTruthy(); // stop
  expect(screen.getByText('$130.00')).toBeTruthy(); // target
  expect(screen.getByTestId('card-disclaimer').textContent).toContain('Informational only.');
});

test('levels-unavailable edge case still renders the card', () => {
  render(
    <PositionCard
      holding={holding({
        levels: {
          original_plan: levelBlock({ levels_state: 'insufficient_data', status: 'insufficient_data' }),
          current_condition: levelBlock({ levels_state: 'insufficient_data', status: 'insufficient_data' }),
        },
        instruction: instruction({ directive: null, status_label: 'Levels unavailable' }),
      })}
      directiveEnabled
      disclaimer="Informational only."
    />,
  );
  expect(screen.getByTestId('position-card')).toBeTruthy();
  expect(screen.getByTestId('levels-unavailable')).toBeTruthy();
});

test('empty news renders an explicit "nothing new"', () => {
  render(<PositionCard holding={holding()} directiveEnabled={false} disclaimer="d" />);
  expect(screen.getByTestId('events-nothing-new')).toBeTruthy();
});

test('sentiment section renders (stubbed lazy child) without blocking the shell', () => {
  render(<PositionCard holding={holding()} directiveEnabled={false} disclaimer="d" />);
  expect(screen.getByTestId('sentiment-stub')).toBeTruthy();
});

test('directive_enabled=false shows the neutral status label and no verb (FR-008)', () => {
  render(
    <PositionCard
      holding={holding({ instruction: instruction({ directive: 'sell', status_label: 'Stop breached' }) })}
      directiveEnabled={false}
      disclaimer="d"
    />,
  );
  expect(screen.getByTestId('instruction-status').textContent).toContain('Stop breached');
  expect(screen.queryByTestId('instruction-directive')).toBeNull();
});

test('directive_enabled=true renders the Hold/Trim/Sell verb', () => {
  render(
    <PositionCard
      holding={holding({ instruction: instruction({ directive: 'sell', status_label: 'Stop breached' }) })}
      directiveEnabled
      disclaimer="d"
    />,
  );
  expect(screen.getByTestId('instruction-directive').textContent).toContain('Sell');
});
