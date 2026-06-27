import { render, screen } from '@testing-library/react';
import { describe, expect, test } from 'vitest';
import { EntryReadinessDetails } from '../../src/components/EntryReadinessDetails';
import type { Candidate } from '../../src/lib/api';

const entryTiming: NonNullable<Candidate['entry_timing']> = {
  state: 'not_entry_ready',
  components: [
    { name: 'pivot_proximity', status: 'pass', value: 0.03, reason: 'near pivot' },
    { name: 'trend', status: 'pass', value: 1, reason: 'above 200-day SMA' },
    { name: 'volume_confirmation', status: 'fail', value: 1.1, reason: 'volume below threshold' },
    { name: 'base_maturity', status: 'pass', value: 7, reason: 'mature base' },
    { name: 'base_depth', status: 'pass', value: 0.22, reason: 'base depth in range' },
    { name: 'not_extended', status: 'pass', value: 0.15, reason: 'not extended from SMA-200' },
  ],
  disqualifiers: [
    {
      name: 'huge_gap',
      triggered: true,
      value: 0.08,
      reason: 'gap above pivot exceeds threshold',
      forces_not_entry_ready: true,
    },
  ],
  diagnostics: {
    pivot: 100,
    base_type: 'cup_with_handle',
    base_length_weeks: 7,
    base_depth: 0.22,
    breakout_volume_ratio: 1.1,
    dist_above_pivot: 0.03,
    dist_above_sma_200: 0.15,
  },
  summary: 'near pivot, but volume confirmation is weak',
};

describe('EntryReadinessDetails', () => {
  test('renders entry readiness state, components, diagnostics, and disqualifiers', () => {
    render(<EntryReadinessDetails entryTiming={entryTiming} />);

    expect(screen.getByText('Entry readiness')).toBeTruthy();
    expect(screen.getByText('Not entry-ready')).toBeTruthy();
    expect(screen.getByText('near pivot, but volume confirmation is weak')).toBeTruthy();
    expect(screen.getByText('pivot proximity')).toBeTruthy();
    expect(screen.getAllByText(/3\.0%/).length).toBeGreaterThan(0);
    expect(screen.getByText('cup-with-handle')).toBeTruthy();
    expect(screen.getByText('1.10x')).toBeTruthy();
    expect(screen.getByText('huge gap flagged')).toBeTruthy();
  });
});
