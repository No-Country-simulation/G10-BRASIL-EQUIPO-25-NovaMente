import { defineConfig, devices } from '@playwright/test';

// Os testes partem de quem já escolheu os cookies (preferências permitidas): sem isso o
// aviso cobriria o rodapé da tela e seguraria o tour. O 13-privacidade.spec.ts parte do zero.
const CONSENTIMENTO_JA_ESCOLHIDO = {
  cookies: [],
  origins: [
    {
      origin: 'http://localhost:3000',
      localStorage: [
        {
          name: 'novamente.consentimento',
          value: JSON.stringify({
            versao: 1,
            preferencias: true,
            decidido_em: '2026-11-21T12:00:00.000Z',
          }),
        },
      ],
    },
  ],
};

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  timeout: 120_000,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: 'http://localhost:3000',
    trace: 'on-first-retry',
    acceptDownloads: true,
    navigationTimeout: 60_000,
    storageState: CONSENTIMENTO_JA_ESCOLHIDO,
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
