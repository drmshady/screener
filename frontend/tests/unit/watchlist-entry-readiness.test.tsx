/**
 * T031 (US4): Vitest unit test for the watchlist "watch until entry-ready" view.
 *
 * Tests:
 *  - Entry-ready saved candidate is highlighted as "Entry ready"
 *  - not_entry_ready shows "Watching — not yet ready" with its top failing reasons
 *  - undetermined / insufficient-data (entry_timing null) shows an "Undetermined" state
 *  - last-checked data_as_of is surfaced
 *  - entry-ready sorts ahead of not-yet-ready
 *  - zero directive copy (no "Buy", "Sell", "Recommended", "Strong buy")
 */

import { render, screen } from '@testing-library/react';
import { describe, expect, test, vi, beforeEach } from 'vitest';

const savedEntry = (ticker: string, name: string) => ({
  id: `midterm_52w_high_momentum-${ticker}`,
  ticker,
  name,
  sector: 'Information Technology',
  strategy_slug: 'midterm_52w_high_momentum',
  saved_at: '2026-06-20T10:00:00Z',
  state: 'saved' as const,
  levels_snapshot: { entry: '100.00', stop_loss: '90.00', take_profit: '130.00' },
});

const sampleWatchlist = [
  savedEntry('BBB', 'Beta Corp'), // not ready (listed first to prove sorting)
  savedEntry('AAA', 'Alpha Corp'), // ready
  savedEntry('CCC', 'Gamma Corp'), // undetermined (out of coverage)
  { ...savedEntry('DDD', 'Delta Corp'), state: 'dismissed' as const }, // excluded
];

vi.mock('../../src/lib/store', () => ({
  useAppStore: vi.fn((selector) =>
    selector({
      watchlist: sampleWatchlist,
      updateWatchlistState: vi.fn(),
      setWatchlistEntryStatus: vi.fn(),
    }),
  ),
}));

vi.mock('../../src/lib/api', () => ({
  fetchEntryStatus: vi.fn(async (ticker: string) => {
    if (ticker === 'AAA') {
      return {
        ticker,
        entry_timing: {
          state: 'entry_ready',
          summary: 'Breakout confirmed above pivot.',
          components: [
            { name: 'pivot_proximity', status: 'pass', reason: 'At pivot.' },
            { name: 'volume_confirmation', status: 'pass', reason: 'Volume above average.' },
          ],
        },
        data_as_of: '2026-06-30T21:00:00Z',
        disclaimer: 'For informational purposes only; not investment advice.',
      };
    }
    if (ticker === 'BBB') {
      return {
        ticker,
        entry_timing: {
          state: 'not_entry_ready',
          summary: 'Price is below the pivot.',
          components: [
            { name: 'pivot_proximity', status: 'fail', reason: 'Price 4% below pivot.' },
            { name: 'volume_confirmation', status: 'fail', reason: 'Volume below average.' },
            { name: 'trend', status: 'pass', reason: 'Above the 200-day average.' },
          ],
        },
        data_as_of: '2026-06-30T21:00:00Z',
        disclaimer: 'For informational purposes only; not investment advice.',
      };
    }
    return {
      ticker,
      entry_timing: null,
      data_as_of: '2026-06-30T21:00:00Z',
      disclaimer: 'For informational purposes only; not investment advice.',
    };
  }),
}));

import WatchlistPage from '../../src/app/watchlist/page';

beforeEach(() => {
  vi.clearAllMocks();
});

describe('Watchlist entry-readiness view', () => {
  test('highlights an entry-ready saved candidate', async () => {
    render(<WatchlistPage />);
    expect(await screen.findByText('Entry ready')).toBeTruthy();
  });

  test('shows "Watching — not yet ready" with top failing reasons', async () => {
    render(<WatchlistPage />);
    expect(await screen.findByText(/Watching — not yet ready/)).toBeTruthy();
    expect(await screen.findByText(/Price 4% below pivot\./)).toBeTruthy();
    expect(screen.getByText(/Volume below average\./)).toBeTruthy();
  });

  test('renders an undetermined state for an out-of-coverage ticker', async () => {
    render(<WatchlistPage />);
    expect(await screen.findByText('Undetermined')).toBeTruthy();
  });

  test('excludes dismissed entries from the live view', async () => {
    render(<WatchlistPage />);
    await screen.findByText('Entry ready');
    expect(screen.queryByText('DDD')).toBeNull();
  });

  test('surfaces the last-checked data_as_of', async () => {
    render(<WatchlistPage />);
    expect(await screen.findAllByText(/Last checked/i)).toBeTruthy();
  });

  test('sorts entry-ready ahead of not-yet-ready', async () => {
    render(<WatchlistPage />);
    await screen.findByText('Entry ready');
    const tickers = screen.getAllByTestId('watchlist-ticker').map((el) => el.textContent);
    expect(tickers.indexOf('AAA')).toBeLessThan(tickers.indexOf('BBB'));
  });

  test('no directive copy in the watchlist view', async () => {
    render(<WatchlistPage />);
    await screen.findByText('Entry ready');
    const html = document.body.textContent ?? '';
    for (const word of ['Buy', 'Sell', 'Recommended', 'Strong buy']) {
      expect(html).not.toContain(word);
    }
  });
});
