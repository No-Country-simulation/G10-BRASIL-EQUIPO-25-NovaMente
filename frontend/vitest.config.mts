import { configDefaults, defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import { fileURLToPath } from 'node:url';

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    css: true,
    // Os specs do Playwright (e2e/) casam com o include padrão do Vitest, mas
    // usam o runner do Playwright: rodá-los aqui quebra a suíte inteira.
    exclude: [...configDefaults.exclude, 'e2e/**', 'storybook-static/**', '.storybook/**'],
    coverage: {
      provider: 'v8',
      include: ['src/features/**/*.{ts,tsx}', 'src/services/**/*.{ts,tsx}'],
      thresholds: { lines: 80, statements: 80, functions: 80, branches: 70 },
    },
  },
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
});
