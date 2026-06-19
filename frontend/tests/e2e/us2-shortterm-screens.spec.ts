import { expect, test } from '@playwright/test';
import { COPY } from '../../src/lib/copy';

const strategies = [
  {
    slug: 'shortterm_minervini_vcp',
    heading: 'Short-Term Minervini VCP',
    citation: 'Minervini',
  },
  {
    slug: 'shortterm_atr_breakout',
    heading: 'Short-Term ATR Breakout',
    citation: 'Wilder',
  },
];

for (const strategy of strategies) {
  test(`${strategy.heading} renders as a short-term screen`, async ({ page }) => {
    await page.goto(`/screen/${strategy.slug}`);

    await expect(page.getByRole('heading', { name: strategy.heading })).toBeVisible();
    await expect(page.getByText('Short-term').first()).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Strategy gates' })).toBeVisible();
    await expect(page.getByText(strategy.citation).first()).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Walk-forward metrics' })).toBeVisible();
    await expect(page.getByText('2008-01-01 to 2024-12-31')).toBeVisible();
    await expect(page.getByText(COPY.GLOBAL.DISCLAIMER)).toBeVisible();

    await page.getByRole('button', { name: COPY.SCREENER.RUN_SCREEN }).click();
    await expect(page.getByRole('heading', { name: 'Candidates' })).toBeVisible({ timeout: 30_000 });
    await expect(page.getByText(/matches for \d{4}-\d{2}-\d{2}/)).toBeVisible();
    const resultSurface = page.getByText('Stop / Distance').or(page.getByText('No candidates matched the active filters.'));
    await expect(resultSurface.first()).toBeVisible();
  });
}

function risk(candidate: { entry: string; stop_loss: string }) {
  return (Number(candidate.entry) - Number(candidate.stop_loss)) / Number(candidate.entry);
}

test('ATR breakout produces tighter stops than the mid-term strategy on the current real-data snapshot', async ({ request }) => {
  const apiBase = 'http://127.0.0.1:8100';
  const midterm = await request.post(`${apiBase}/strategies/midterm_52w_high_momentum/run`, {
    data: { parameters: { regime_gate: false }, filters: { shariah_only: false, exclude_earnings_within_days: 0 } },
  });
  const atr = await request.post(`${apiBase}/strategies/shortterm_atr_breakout/run`, {
    data: { parameters: { regime_gate: false }, filters: { shariah_only: false, exclude_earnings_within_days: 0 } },
  });

  expect(midterm.ok()).toBeTruthy();
  expect(atr.ok()).toBeTruthy();
  const midtermBody = await midterm.json();
  const atrBody = await atr.json();
  expect(midtermBody.candidate_count).toBeGreaterThan(0);
  expect(atrBody.candidate_count).toBeGreaterThan(0);

  type ApiCandidate = { ticker: string; entry: string; stop_loss: string };
  const midtermCandidates = midtermBody.candidates as ApiCandidate[];
  const atrCandidates = atrBody.candidates as ApiCandidate[];
  const midtermByTicker = new Map<string, ApiCandidate>(
    midtermCandidates.map((candidate) => [candidate.ticker, candidate]),
  );
  const overlappingAtr = atrCandidates.find((candidate) => midtermByTicker.has(candidate.ticker));
  const midtermRisk = overlappingAtr
    ? risk(midtermByTicker.get(overlappingAtr.ticker)!)
    : Math.min(...midtermCandidates.map(risk));
  const atrRisk = overlappingAtr ? risk(overlappingAtr) : Math.min(...atrCandidates.map(risk));

  expect(atrRisk).toBeGreaterThan(0);
  expect(atrRisk).toBeLessThan(midtermRisk);
});
