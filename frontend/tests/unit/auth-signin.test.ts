import { afterEach, describe, expect, test, vi } from 'vitest';

async function signIn(profile: { email?: string; email_verified?: boolean }) {
  vi.resetModules();
  const { authOptions } = await import('../../src/auth');
  const callback = authOptions.callbacks?.signIn;
  if (!callback) {
    throw new Error('signIn callback missing');
  }
  return callback({
    user: { id: 'user-1', email: profile.email },
    account: null,
    profile,
    email: undefined,
    credentials: undefined,
  });
}

function setAuthEnv() {
  process.env.AUTH_GOOGLE_ID = 'google-id';
  process.env.AUTH_GOOGLE_SECRET = 'google-secret';
  process.env.AUTH_SECRET = 'auth-secret';
  process.env.SCREENER_OWNER_EMAIL = 'Owner@Example.com';
}

describe('owner sign-in allowlist', () => {
  afterEach(() => {
    delete process.env.AUTH_GOOGLE_ID;
    delete process.env.AUTH_GOOGLE_SECRET;
    delete process.env.AUTH_SECRET;
    delete process.env.SCREENER_OWNER_EMAIL;
    vi.resetModules();
  });

  test('admits a verified Google profile matching the owner email case-insensitively', async () => {
    setAuthEnv();

    await expect(
      signIn({ email: 'owner@example.com', email_verified: true }),
    ).resolves.toBe(true);
  });

  test('denies a matching email when Google did not verify it', async () => {
    setAuthEnv();

    await expect(
      signIn({ email: 'owner@example.com', email_verified: false }),
    ).resolves.toBe(false);
  });

  test('denies any non-owner email', async () => {
    setAuthEnv();

    await expect(
      signIn({ email: 'other@example.com', email_verified: true }),
    ).resolves.toBe(false);
  });

  test('fails closed when required auth environment is missing', async () => {
    process.env.AUTH_GOOGLE_ID = 'google-id';
    process.env.AUTH_GOOGLE_SECRET = 'google-secret';
    process.env.AUTH_SECRET = 'auth-secret';

    await expect(
      signIn({ email: 'owner@example.com', email_verified: true }),
    ).resolves.toBe(false);
  });
});
