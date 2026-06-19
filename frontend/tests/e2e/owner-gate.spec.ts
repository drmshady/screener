import { expect, test } from '@playwright/test';
import { encode } from 'next-auth/jwt';

const hostedAuthConfigured =
  process.env.SCREENER_HOSTED_MODE === '1' &&
  process.env.AUTH_SECRET &&
  process.env.SCREENER_OWNER_EMAIL;

test.describe('owner gate', () => {
  test.skip(!hostedAuthConfigured, 'requires hosted-mode auth env');

  test('unauthenticated visitors are redirected before app data renders', async ({ page }) => {
    await page.goto('/screen/midterm_52w_high_momentum');

    await expect(page).toHaveURL(/\/api\/auth\/signin/);
    await expect(page.getByText('Recommended Stocks')).toHaveCount(0);
  });

  test('non-owner session is denied', async ({ page, context, baseURL }) => {
    const token = await encode({
      secret: process.env.AUTH_SECRET!,
      token: { email: 'other@example.com', name: 'Other User', sub: 'other' },
    });
    await context.addCookies([
      {
        name: 'next-auth.session-token',
        value: token,
        url: baseURL!,
        httpOnly: true,
        sameSite: 'Lax',
      },
    ]);

    await page.goto('/screen/midterm_52w_high_momentum');

    await expect(page).toHaveURL(/\/api\/auth\/signin/);
    await expect(page.getByText('Recommended Stocks')).toHaveCount(0);
  });

  test('owner session can reach the app shell', async ({ page, context, baseURL }) => {
    const token = await encode({
      secret: process.env.AUTH_SECRET!,
      token: {
        email: process.env.SCREENER_OWNER_EMAIL!,
        name: 'Owner',
        sub: 'owner',
      },
    });
    await context.addCookies([
      {
        name: 'next-auth.session-token',
        value: token,
        url: baseURL!,
        httpOnly: true,
        sameSite: 'Lax',
      },
    ]);

    await page.goto('/');

    await expect(page.getByRole('link', { name: 'Screens' })).toBeVisible();
  });
});
