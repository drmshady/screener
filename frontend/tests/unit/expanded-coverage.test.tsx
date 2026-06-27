import { render, screen } from '@testing-library/react';
import { describe, expect, test } from 'vitest';
import { CandidateRow } from '../../src/components/CandidateRow';
import { StrategyGatesPanel } from '../../src/components/StrategyGatesPanel';
import type { Candidate, Strategy } from '../../src/lib/api';

const baseCandidate: Candidate = {
  ticker: 'WARNED',
  name: 'Warned Corp',
  sector: 'Technology',
  strategy_slug: 'midterm_52w_high_momentum',
  strategy_name: 'Mid-Term 52-Week High Momentum',
  timeframe: 'Mid-term',
  current_price: '102.00',
  entry: '102.00',
  stop_loss: '94.00',
  take_profit: '120.00',
  rank: 5,
  score: 0.9,
  reason: 'Within 5% of 52-week high',
  gate_results: [],
  warnings: ['Sector strength'],
  skipped_gates: [{ gate: 'Sector strength', reason: 'outside the leading sectors by proximity to highs' }],
  data_integrity_warnings: [],
  data_suspect: false,
  recent_8k_count_30d: 0,
  events_source_as_of: null,
};

const momentumStrategy: Strategy = {
  slug: 'midterm_52w_high_momentum',
  name: 'Mid-Term 52-Week High Momentum',
  timeframe: 'Mid-term',
  citation: 'George & Hwang (2004)',
  description: 'Ranks liquid stocks near their 52-week high.',
  holding_period_days: { min: 60, max: 180 },
  parameters: {},
  regime_favorability: { 'Trending up': 'Favorable' },
  default_exclude_earnings_within_days: 0,
  enabled_by_default: true,
  modifications: [],
  backtest_summary: null,
};

describe('expanded coverage (US2) rendering', () => {
  test('candidate row shows a skipped-gate badge with the reason', () => {
    render(
      <table>
        <tbody>
          <CandidateRow candidate={baseCandidate} strategySlug="midterm_52w_high_momentum" />
        </tbody>
      </table>,
    );
    const badge = screen.getByText(/preferred gate skipped/i);
    expect(badge).toBeTruthy();
    expect(badge.getAttribute('title')).toContain('outside the leading sectors');
  });

  test('an empty skipped_gates list renders no badge', () => {
    render(
      <table>
        <tbody>
          <CandidateRow
            candidate={{ ...baseCandidate, skipped_gates: [], warnings: [] }}
            strategySlug="midterm_52w_high_momentum"
          />
        </tbody>
      </table>,
    );
    expect(screen.queryByText(/preferred gate skipped/i)).toBeNull();
  });

  test('strategy gates panel shows the three-tier map for momentum', () => {
    render(<StrategyGatesPanel strategy={momentumStrategy} />);
    expect(screen.getByText('Gate tiers (expanded coverage)')).toBeTruthy();
    expect(screen.getByText('Essential')).toBeTruthy();
    expect(screen.getByText('Preferred')).toBeTruthy();
    expect(screen.getByText('Disqualifier')).toBeTruthy();
    expect(screen.getByText('Relative strength')).toBeTruthy();
  });

  test('new expanded-coverage copy is directive-free', () => {
    const { container: rowContainer } = render(
      <table>
        <tbody>
          <CandidateRow candidate={baseCandidate} strategySlug="midterm_52w_high_momentum" />
        </tbody>
      </table>,
    );
    const { container: panelContainer } = render(<StrategyGatesPanel strategy={momentumStrategy} />);
    const text = `${rowContainer.textContent ?? ''} ${panelContainer.textContent ?? ''}`.toLowerCase();
    expect(text).not.toContain('buy');
    expect(text).not.toContain('sell');
    expect(text).not.toContain('recommended');
    expect(text).not.toContain('strong buy');
  });
});
