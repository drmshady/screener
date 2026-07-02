import { render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, test, vi } from 'vitest';
import { RegimePanel } from '../../src/components/RegimePanel';
import { fetchApi } from '../../src/lib/api';

vi.mock('../../src/lib/api', async () => {
  const actual = await vi.importActual<typeof import('../../src/lib/api')>('../../src/lib/api');
  return {
    ...actual,
    fetchApi: vi.fn(),
  };
});

const baseRegime = {
  regime: 'Trending up',
  rule_summary: 'Trending up: SPY is above its 200-day SMA.',
  inputs: {
    spy_close: 561.23,
    spy_sma200: 542.1,
    spy_above_sma200: true,
    breadth_pct_above_sma200: 0.61,
    breadth_above_count: 61,
    breadth_eligible_count: 100,
    breadth_total_constituents: 120,
    price_source_name: 'baked(daily)',
    unavailable_reason: null,
    breadth_source_name: 'Stooq',
    breadth_source_as_of: '2026-01-31T00:00:00Z',
  },
  as_of_date: '2026-01-31',
  per_strategy_favorability: [],
  data_as_of: '2026-01-31T00:00:00Z',
  disclaimer: 'Informational only.',
} as const;

describe('RegimePanel', () => {
  beforeEach(() => {
    vi.mocked(fetchApi).mockReset();
  });

  test('renders numeric SPY regime inputs with verdict, source, and as-of', async () => {
    vi.mocked(fetchApi).mockResolvedValue(baseRegime);

    render(<RegimePanel />);

    await waitFor(() => expect(screen.getAllByText('561.23').length).toBeGreaterThan(0));
    expect(screen.getAllByText('542.10').length).toBeGreaterThan(0);
    expect(screen.getByText('Above SMA 200')).toBeTruthy();
    expect(screen.getByText('baked(daily)')).toBeTruthy();
    expect(screen.getAllByText('As of 2026-01-31').length).toBeGreaterThan(0);
    expect(screen.queryByText(/Unknown/i)).toBeNull();
  });

  test('renders explicit unavailable reason instead of Unknown', async () => {
    vi.mocked(fetchApi).mockResolvedValue({
      ...baseRegime,
      regime: 'Range-bound',
      rule_summary: 'Range-bound: SPY 200-day SMA input is unavailable.',
      inputs: {
        ...baseRegime.inputs,
        spy_sma200: null,
        spy_above_sma200: null,
        unavailable_reason: 'Insufficient SPY history for a 200-day SMA; regime gate fails open.',
      },
    });

    render(<RegimePanel />);

    await waitFor(() => expect(screen.getAllByText(/Insufficient SPY history/).length).toBeGreaterThan(0));
    expect(screen.getAllByText('Unavailable').length).toBeGreaterThan(0);
    expect(screen.queryByText(/Unknown/i)).toBeNull();
  });
});
