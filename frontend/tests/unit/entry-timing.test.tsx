import { render, screen } from '@testing-library/react';
import { describe, expect, test } from 'vitest';
import { CandidateRow } from '../../src/components/CandidateRow';
import { CandidateSchema } from '../../src/lib/api';
import type { Candidate } from '../../src/lib/api';

const baseCandidate: Candidate = {
  ticker: 'TEST',
  name: 'Test Corp',
  sector: 'Technology',
  strategy_slug: 'midterm_52w_high_momentum',
  strategy_name: 'Mid-Term 52-Week High Momentum',
  timeframe: 'Mid-term',
  current_price: '102.00',
  entry: '102.00',
  stop_loss: '94.00',
  take_profit: '120.00',
  rank: 1,
  score: 1.2,
  reason: 'Within 5% of 52-week high',
  gate_results: [],
  warnings: [],
  data_integrity_warnings: [],
  data_suspect: false,
  recent_8k_count_30d: 0,
  events_source_as_of: null,
  entry_timing: {
    state: 'entry_ready',
    components: [
      { name: 'pivot_proximity', status: 'pass', value: 0.02, reason: 'near pivot' },
      { name: 'trend', status: 'pass', value: 1, reason: 'above 200-day SMA' },
      { name: 'volume_confirmation', status: 'pass', value: 1.5, reason: 'confirming volume' },
      { name: 'base_maturity', status: 'pass', value: 6, reason: 'mature base' },
      { name: 'base_depth', status: 'pass', value: 0.18, reason: 'base depth in range' },
      { name: 'not_extended', status: 'pass', value: 0.13, reason: 'not extended from SMA-200' },
    ],
    disqualifiers: [],
    diagnostics: {
      pivot: 100,
      base_type: 'flat',
      base_length_weeks: 6,
      base_depth: 0.18,
      breakout_volume_ratio: 1.5,
      dist_above_pivot: 0.02,
      dist_above_sma_200: 0.13,
    },
    summary: 'near pivot, uptrend, confirming volume',
  },
};

describe('entry timing rendering', () => {
  test('renders neutral state, components, and diagnostics', () => {
    render(
      <table>
        <tbody>
          <CandidateRow candidate={baseCandidate} strategySlug="midterm_52w_high_momentum" />
        </tbody>
      </table>,
    );

    expect(screen.getByText('Entry-ready')).toBeTruthy();
    expect(screen.getByText('near pivot, uptrend, confirming volume')).toBeTruthy();
    expect(screen.getByText('pivot 100.00')).toBeTruthy();
    expect(screen.getByText('flat base')).toBeTruthy();
    expect(screen.getByText('pivot proximity')).toBeTruthy();
  });

  test('copy remains directive-free', () => {
    const { container } = render(
      <table>
        <tbody>
          <CandidateRow candidate={baseCandidate} strategySlug="midterm_52w_high_momentum" />
        </tbody>
      </table>,
    );
    const text = container.textContent?.toLowerCase() ?? '';

    expect(text).not.toContain('buy');
    expect(text).not.toContain('sell');
    expect(text).not.toContain('recommended');
    expect(text).not.toContain('strong buy');
  });

  test('baseline candidate payloads remain compatible when entry fields are absent', () => {
    const parsed = CandidateSchema.parse({
      ...baseCandidate,
      entry_timing: undefined,
      skipped_gates: undefined,
    });

    expect(parsed.entry_timing).toBeUndefined();
    expect(parsed.skipped_gates).toEqual([]);
  });
});
