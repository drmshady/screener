/**
 * Feature 014: Vitest unit test for CopyHoldingAdvisorPrompt.
 *
 * Tests:
 *  - Per-holding button (ticker) calls the single-holding client and shows the preview
 *  - Whole-portfolio button (no ticker) calls the portfolio client
 *  - Copied preview renders the backend prompt text
 *  - Zero directive copy in the rendered prompt preview (non-directive mode)
 *  - Directive mode marks the preview with data-personal-use-prompt
 */

import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, expect, test, vi, beforeEach } from 'vitest';

const fetchHoldingAdvisorPrompt = vi.fn();
const fetchPortfolioAdvisorPrompt = vi.fn();

vi.mock('@/lib/api', () => ({
  fetchHoldingAdvisorPrompt: (...args: unknown[]) => fetchHoldingAdvisorPrompt(...args),
  fetchPortfolioAdvisorPrompt: (...args: unknown[]) => fetchPortfolioAdvisorPrompt(...args),
}));

vi.mock('@/lib/advisorPrompt', () => ({
  copyText: vi.fn(async () => true),
}));

import { CopyHoldingAdvisorPrompt } from '@/components/CopyHoldingAdvisorPrompt';

const NEUTRAL_PROMPT =
  'TASK: review this position the user ALREADY HOLDS.\n## Held position — AAA\n- Suggested size: 40 shares\n## Honesty\n- info only.';

beforeEach(() => {
  fetchHoldingAdvisorPrompt.mockReset();
  fetchPortfolioAdvisorPrompt.mockReset();
});

test('per-holding button fetches the single-holding prompt and shows the preview', async () => {
  fetchHoldingAdvisorPrompt.mockResolvedValue({
    ticker: 'AAA',
    strategy: 'midterm_52w_high_momentum',
    personal_use_directive: false,
    prompt: NEUTRAL_PROMPT,
    data_as_of: '2026-06-12',
    disclaimer: 'info only.',
  });

  render(<CopyHoldingAdvisorPrompt totalCapital="100000" ticker="AAA" />);
  fireEvent.click(screen.getByRole('button', { name: 'Copy prompt' }));

  await waitFor(() => expect(screen.getByTestId('holding-advisor-prompt-preview')).toBeTruthy());
  expect(fetchHoldingAdvisorPrompt).toHaveBeenCalledWith('AAA', {
    total_capital: '100000',
    strategy_slug: undefined,
  });
  const preview = screen.getByTestId('holding-advisor-prompt-preview');
  expect(preview.textContent).toContain('Held position');
  // non-directive: no exemption marker, no directive words
  expect(preview.getAttribute('data-personal-use-prompt')).toBeNull();
  const lower = (preview.textContent ?? '').toLowerCase();
  for (const word of [' buy', ' sell', 'recommended', 'strong buy']) {
    expect(lower).not.toContain(word);
  }
});

test('whole-portfolio button fetches the portfolio prompt', async () => {
  fetchPortfolioAdvisorPrompt.mockResolvedValue({
    strategy: 'midterm_52w_high_momentum',
    holding_count: 2,
    personal_use_directive: false,
    prompt: NEUTRAL_PROMPT,
    data_as_of: '2026-06-12',
    disclaimer: 'info only.',
  });

  render(<CopyHoldingAdvisorPrompt totalCapital="100000" strategySlug="midterm_52w_high_momentum" />);
  fireEvent.click(screen.getByRole('button', { name: 'Copy portfolio prompt' }));

  await waitFor(() => expect(fetchPortfolioAdvisorPrompt).toHaveBeenCalled());
  expect(fetchPortfolioAdvisorPrompt).toHaveBeenCalledWith({
    total_capital: '100000',
    strategy_slug: 'midterm_52w_high_momentum',
  });
});

test('directive mode marks the preview as a personal-use prompt', async () => {
  fetchHoldingAdvisorPrompt.mockResolvedValue({
    ticker: 'AAA',
    strategy: 'midterm_52w_high_momentum',
    personal_use_directive: true,
    prompt: 'TASK: HOLD, TRIM, or EXIT. ## Held position — AAA',
    data_as_of: '2026-06-12',
    disclaimer: 'info only.',
  });

  render(<CopyHoldingAdvisorPrompt totalCapital="100000" ticker="AAA" />);
  fireEvent.click(screen.getByRole('button', { name: 'Copy prompt' }));

  await waitFor(() => expect(screen.getByTestId('holding-advisor-prompt-preview')).toBeTruthy());
  expect(
    screen.getByTestId('holding-advisor-prompt-preview').getAttribute('data-personal-use-prompt'),
  ).toBe('true');
});

test('shows an error message when the fetch fails', async () => {
  fetchHoldingAdvisorPrompt.mockRejectedValue(new Error('boom'));
  render(<CopyHoldingAdvisorPrompt totalCapital="100000" ticker="AAA" />);
  fireEvent.click(screen.getByRole('button', { name: 'Copy prompt' }));
  await waitFor(() => expect(screen.getByText('boom')).toBeTruthy());
});
