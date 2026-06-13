import { test, expect } from '@playwright/test';

// Feature 004 / US1: clicking "Copy advisor prompt" produces a complete,
// non-empty prompt containing the candidate's ticker and the disclaimer.
test('copy advisor prompt yields a complete prompt for a candidate', async ({ page, context }) => {
  await context.grantPermissions(['clipboard-read', 'clipboard-write']);

  // Use the analyze surface (deterministic single-ticker path).
  await page.goto('/analyze');
  await expect(page.getByRole('navigation', { name: 'Primary' })).toBeVisible();

  const symbol = 'AMAT';
  await page.locator('input').first().fill(symbol);
  await page.getByRole('button', { name: 'Analyze' }).click();

  const copyButton = page.getByRole('button', { name: /Copy advisor prompt/i });
  await expect(copyButton).toBeVisible({ timeout: 15000 });
  await copyButton.click();

  const preview = page.getByTestId('advisor-prompt-preview');
  await expect(preview).toBeVisible({ timeout: 15000 });

  const text = (await preview.innerText()).toLowerCase();
  expect(text.length).toBeGreaterThan(200);
  expect(text).toContain(symbol.toLowerCase());
  expect(text).toContain('informational purposes only'); // disclaimer
  expect(text).toContain('survivorship'); // honesty block always present
});
