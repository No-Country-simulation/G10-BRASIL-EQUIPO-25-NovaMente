import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  timeout: 120_000,
  reporter: [['list']],
  use: {
    baseURL: 'http://localhost:3000',
    trace: 'on-first-retry',
    acceptDownloads: true,
    navigationTimeout: 60_000,
  },
  expect: { timeout: 30_000 },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: {
    command: 'npm run dev',
    url: 'http://localhost:3000',
    // Nunca reaproveita um servidor já no ar: um `next dev` sem mock apontaria
    // para o FastAPI real e os testes deixariam de ser determinísticos.
    reuseExistingServer: false,
    timeout: 180_000,
    env: { NEXT_PUBLIC_API_MOCK: '1' },
  },
});
