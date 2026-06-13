import { expect, test } from '@playwright/test';

test('enabled strategy pages expose citations and backtest provenance', async ({ page, request }) => {
  const strategiesResponse = await request.get('http://127.0.0.1:8100/strategies?enabled_only=true');
  expect(strategiesResponse.ok()).toBeTruthy();
  const strategiesBody = await strategiesResponse.json();
  const strategies = strategiesBody.strategies;

  expect(strategies.length).toBeGreaterThan(0);

  for (const strategy of strategies) {
    await page.goto(`/screen/${strategy.slug}`);

    await expect(page.getByRole('heading', { name: strategy.name })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Strategy gates' })).toBeVisible();
    await expect(page.getByText(strategy.citation).first()).toBeVisible();

    for (const modification of strategy.modifications) {
      await expect(page.getByText(modification.name).first()).toBeVisible();
      await expect(page.getByText(modification.citation).first()).toBeVisible();
    }

    const backtestResponse = await request.get(`http://127.0.0.1:8100/strategies/${strategy.slug}/backtest`);
    expect(backtestResponse.ok()).toBeTruthy();
    const backtest = await backtestResponse.json();

    await expect(page.getByRole('heading', { name: 'Walk-forward metrics' })).toBeVisible();
    await expect(
      page.getByText(`${backtest.data_window_start} to ${backtest.data_window_end}`, { exact: false }),
    ).toBeVisible();

    for (const source of backtest.data_sources) {
      await expect(page.getByText(`${source.source_name} as of ${source.source_as_of.slice(0, 10)}`).first()).toBeVisible();
    }
  }
});
