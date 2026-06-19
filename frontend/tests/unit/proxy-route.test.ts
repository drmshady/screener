import { afterEach, describe, expect, test, vi } from 'vitest';

const backendFetch = vi.fn();

vi.mock('server-only', () => ({}));
vi.mock('../../src/auth', () => ({
  authOptions: {},
}));
vi.mock('next-auth', () => ({
  default: () => backendFetch,
  getServerSession: vi.fn(() => Promise.resolve({ user: { email: 'owner@example.com' } })),
}));

function setProxyEnv() {
  process.env.SCREENER_HOSTED_MODE = '1';
  process.env.BACKEND_BASE_URL = 'https://backend.example';
  process.env.SCREENER_OWNER_SECRET = 'owner-secret';
}

describe('BFF proxy route', () => {
  const originalFetch = global.fetch;

  afterEach(() => {
    delete process.env.SCREENER_HOSTED_MODE;
    delete process.env.BACKEND_BASE_URL;
    delete process.env.SCREENER_OWNER_SECRET;
    global.fetch = originalFetch;
    backendFetch.mockReset();
    vi.resetModules();
  });

  test('forwards method, path, query, JSON body, and injects the owner secret server-side', async () => {
    setProxyEnv();
    backendFetch.mockResolvedValue(
      new Response(
        JSON.stringify({
          ok: true,
          data_as_of: '2026-07-06T21:00:00Z',
          disclaimer: 'Informational only.',
        }),
        { status: 202, headers: { 'Content-Type': 'application/json' } },
      ),
    );
    global.fetch = backendFetch as unknown as typeof fetch;

    const { POST } = await import('../../src/app/api/proxy/[...path]/route');
    const request = new Request('http://frontend.test/api/proxy/strategies/demo/run?limit=5', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Connection: 'keep-alive',
        'X-Owner-Secret': 'browser-should-not-win',
      },
      body: JSON.stringify({ filters: { shariah_only: true } }),
    });

    const response = await POST(request, { params: Promise.resolve({ path: ['strategies', 'demo', 'run'] }) });

    expect(backendFetch).toHaveBeenCalledTimes(1);
    const [url, init] = backendFetch.mock.calls[0] as [string, RequestInit];
    expect(url).toBe('https://backend.example/strategies/demo/run?limit=5');
    expect(init.method).toBe('POST');
    expect(init.body).toBe(JSON.stringify({ filters: { shariah_only: true } }));
    expect(new Headers(init.headers).get('X-Owner-Secret')).toBe('owner-secret');
    expect(new Headers(init.headers).get('Connection')).toBeNull();

    expect(response.status).toBe(202);
    await expect(response.json()).resolves.toMatchObject({
      ok: true,
      data_as_of: '2026-07-06T21:00:00Z',
      disclaimer: 'Informational only.',
    });
  });

  test('returns backend errors unchanged so ApiError retry semantics are preserved', async () => {
    setProxyEnv();
    backendFetch.mockResolvedValue(
      new Response(JSON.stringify({ detail: 'Backend warming up' }), {
        status: 503,
        headers: { 'Content-Type': 'application/json' },
      }),
    );
    global.fetch = backendFetch as unknown as typeof fetch;

    const { GET } = await import('../../src/app/api/proxy/[...path]/route');
    const response = await GET(
      new Request('http://frontend.test/api/proxy/data/freshness'),
      { params: Promise.resolve({ path: ['data', 'freshness'] }) },
    );

    expect(response.status).toBe(503);
    await expect(response.json()).resolves.toEqual({ detail: 'Backend warming up' });
  });

  test('same-origin API client never exposes backend URL or owner secret', async () => {
    setProxyEnv();
    const { apiBaseUrlForTest } = await import('../../src/lib/api');

    expect(apiBaseUrlForTest()).toBe('/api/proxy');
    expect(JSON.stringify(await import('../../src/lib/api'))).not.toContain('owner-secret');
    expect(JSON.stringify(await import('../../src/lib/api'))).not.toContain('backend.example');
  });
});
