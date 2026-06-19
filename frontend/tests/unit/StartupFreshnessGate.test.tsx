import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, test, vi } from 'vitest';
import { DataFreshnessPanel } from '../../src/components/DataFreshnessPanel';
import { StartupFreshnessGate } from '../../src/components/StartupFreshnessGate';
import {
  DataFreshnessResponse,
  DataRefreshResponse,
  getDataFreshness,
  refreshData,
} from '../../src/lib/api';

vi.mock('../../src/lib/api', async () => {
  const actual = await vi.importActual<typeof import('../../src/lib/api')>(
    '../../src/lib/api',
  );
  return {
    ...actual,
    getDataFreshness: vi.fn(),
    refreshData: vi.fn(),
  };
});

const currentFreshness: DataFreshnessResponse = {
  sources: [
    {
      source_name: 'yfinance',
      kind: 'prices',
      data_as_of: '2026-07-06',
      latest_session: '2026-07-06',
      sessions_behind: 0,
      is_stale: false,
      last_refresh_outcome: 'skipped-current',
    },
  ],
  any_stale: false,
  latest_session: '2026-07-06',
  data_as_of: '2026-07-06T22:00:00Z',
  disclaimer: 'Informational only.',
};

const staleFreshness: DataFreshnessResponse = {
  sources: [
    {
      source_name: 'yfinance',
      kind: 'prices',
      data_as_of: '2026-07-02',
      latest_session: '2026-07-06',
      sessions_behind: 1,
      is_stale: true,
      last_refresh_outcome: 'failed',
    },
  ],
  any_stale: true,
  latest_session: '2026-07-06',
  data_as_of: '2026-07-06T22:00:00Z',
  disclaimer: 'Informational only.',
};

const missingSnapshotFreshness: DataFreshnessResponse = {
  sources: [
    {
      source_name: 'yfinance',
      kind: 'prices',
      data_as_of: null,
      latest_session: '2026-07-06',
      sessions_behind: null,
      is_stale: true,
      last_refresh_outcome: 'failed',
    },
    {
      source_name: 'stooq',
      kind: 'prices',
      data_as_of: null,
      latest_session: '2026-07-06',
      sessions_behind: null,
      is_stale: true,
      last_refresh_outcome: 'failed',
    },
  ],
  any_stale: true,
  latest_session: '2026-07-06',
  data_as_of: '2026-07-06T22:00:00Z',
  disclaimer: 'Informational only.',
};

const refreshResult: DataRefreshResponse = {
  refreshed_tickers: 10,
  fetched_rows: 20,
  latest_bar: '2026-07-06',
  capped: false,
  notices: [],
  data_as_of: '2026-07-06T22:05:00Z',
  disclaimer: 'Informational only.',
};

describe('StartupFreshnessGate', () => {
  beforeEach(() => {
    delete process.env.NEXT_PUBLIC_SCREENER_HOSTED_MODE;
    delete process.env.SCREENER_HOSTED_MODE;
    vi.mocked(getDataFreshness).mockReset();
    vi.mocked(refreshData).mockReset();
  });

  test('stale data prompts for refresh or cached-data proceed', async () => {
    vi.mocked(getDataFreshness).mockResolvedValue(staleFreshness);

    render(<StartupFreshnessGate />);

    expect(await screen.findByText('Cached data needs attention')).toBeTruthy();
    expect(screen.getByText('yfinance as of 2026-07-02')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Refresh now' })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Proceed on cached data' })).toBeTruthy();
  });

  test('current data reports the latest completed session without prompting', async () => {
    vi.mocked(getDataFreshness).mockResolvedValue(currentFreshness);

    render(<StartupFreshnessGate />);

    expect(
      await screen.findByText('Data is current for latest completed session 2026-07-06.'),
    ).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Refresh now' })).toBeNull();
  });

  test('unreachable freshness endpoint leaves app usable with a notice', async () => {
    vi.mocked(getDataFreshness).mockRejectedValue(new Error('offline'));

    render(<StartupFreshnessGate />);

    expect(
      await screen.findByText('Data freshness check unavailable. Cached data remains usable.'),
    ).toBeTruthy();
  });

  test('refresh now posts refresh and rechecks freshness', async () => {
    vi.mocked(getDataFreshness)
      .mockResolvedValueOnce(staleFreshness)
      .mockResolvedValueOnce(currentFreshness);
    vi.mocked(refreshData).mockResolvedValue(refreshResult);

    render(<StartupFreshnessGate />);

    fireEvent.click(await screen.findByRole('button', { name: 'Refresh now' }));

    await waitFor(() => expect(refreshData).toHaveBeenCalledWith('US'));
    expect(
      await screen.findByText('Data is current for latest completed session 2026-07-06.'),
    ).toBeTruthy();
  });

  test('no published snapshot shows an explicit maintenance state, not an error', async () => {
    vi.mocked(getDataFreshness).mockResolvedValue(missingSnapshotFreshness);

    render(<StartupFreshnessGate />);

    expect(await screen.findByText('Data snapshot unavailable')).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Refresh now' })).toBeNull();
    expect(screen.queryByRole('button', { name: 'Proceed on cached data' })).toBeNull();
  });

  test('hosted mode points to local republish and does not offer heavy refresh', async () => {
    process.env.NEXT_PUBLIC_SCREENER_HOSTED_MODE = '1';
    vi.mocked(getDataFreshness).mockResolvedValue(staleFreshness);

    render(<StartupFreshnessGate />);

    expect(await screen.findByText('Cached data needs attention')).toBeTruthy();
    expect(screen.getByText(/Refresh the local snapshot and republish/)).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Refresh now' })).toBeNull();
    expect(screen.getByRole('button', { name: 'Proceed on cached data' })).toBeTruthy();
  });
});

describe('DataFreshnessPanel hosted mode', () => {
  beforeEach(() => {
    delete process.env.NEXT_PUBLIC_SCREENER_HOSTED_MODE;
    delete process.env.SCREENER_HOSTED_MODE;
    vi.mocked(getDataFreshness).mockReset();
    vi.mocked(refreshData).mockReset();
  });

  test('explains local republish and suppresses the refresh button', async () => {
    process.env.NEXT_PUBLIC_SCREENER_HOSTED_MODE = '1';
    vi.mocked(getDataFreshness).mockResolvedValue(staleFreshness);

    render(<DataFreshnessPanel />);

    expect(await screen.findByText('Prices as of 2026-07-02')).toBeTruthy();
    expect(screen.getByText(/Refresh the local snapshot and republish/)).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Refresh' })).toBeNull();
  });
});
