import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests/e2e',
  timeout: 60_000,
  use: {
    baseURL: 'http://127.0.0.1:3100',
    trace: 'on-first-retry',
  },
  webServer: [
    {
      command: 'py -3.12 -m uvicorn backend.src.api.app:app --host 127.0.0.1 --port 8100',
      cwd: '..',
      url: 'http://127.0.0.1:8100/healthz',
      reuseExistingServer: false,
      timeout: 60_000,
    },
    {
      command: 'set NEXT_PUBLIC_API_URL=http://127.0.0.1:8100&& npm.cmd run dev -- --hostname 127.0.0.1 --port 3100',
      url: 'http://127.0.0.1:3100',
      reuseExistingServer: false,
      timeout: 60_000,
    },
  ],
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
});
