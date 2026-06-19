import { render, screen } from '@testing-library/react';
import { describe, expect, test } from 'vitest';
import { fetchApi } from '../../src/lib/api';
import { ScreenerTable } from '../../src/components/ScreenerTable';
import { z } from 'zod';

describe('phase 6 error and empty states', () => {
  test('screener table renders an explicit empty state instead of an empty table', () => {
    render(<ScreenerTable candidates={[]} />);

    expect(screen.getByText('No candidates matched the active filters.')).toBeTruthy();
    expect(screen.getByText(/Review the data completeness notes/)).toBeTruthy();
    expect(screen.queryByRole('table')).toBeNull();
  });

  test('fetchApi turns backend failures into retryable human-readable errors', async () => {
    const originalFetch = global.fetch;
    global.fetch = (() =>
      Promise.resolve(
        new Response(JSON.stringify({ detail: 'Backtest temporarily unavailable' }), {
          status: 503,
          headers: { 'Content-Type': 'application/json' },
        }),
      )) as typeof fetch;

    await expect(fetchApi('/strategies/demo/backtest', z.object({ ok: z.boolean() }))).rejects.toMatchObject({
      name: 'ApiError',
      status: 503,
      retryable: true,
      message: 'Backtest temporarily unavailable',
    });

    global.fetch = originalFetch;
  });
});
