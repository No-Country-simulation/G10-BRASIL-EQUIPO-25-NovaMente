import { expect, test } from '@playwright/test';

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    window.localStorage.setItem(
      'novamente.tour',
      JSON.stringify({ versao: 1, concluido_em: new Date().toISOString() }),
    );
  });
});

test('alterna o modo, persiste e troca o logo', async ({ page }) => {
  await page.goto('/');

  await expect(page.locator('html')).toHaveAttribute('data-modo', 'dark');
  await expect(page.locator('.logo-para-modo-escuro').first()).toBeVisible();

  await page.getByRole('button', { name: /ativar modo claro/i }).click();

  await expect(page.locator('html')).toHaveAttribute('data-modo', 'light');
  await expect(page.locator('.logo-para-modo-claro').first()).toBeVisible();
  await expect(page.locator('.logo-para-modo-escuro').first()).toBeHidden();

  const persistido = await page.evaluate(() =>
    JSON.parse(window.localStorage.getItem('novamente.skin') ?? '{}'),
  );
  expect(persistido.state.modo).toBe('light');

  await page.reload();
  await expect(page.locator('html')).toHaveAttribute('data-modo', 'light');
  await expect(page.locator('.logo-para-modo-claro').first()).toBeVisible();
});

test('combina modo claro com o acento ciano', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: /ativar modo claro/i }).click();
  await page.getByRole('button', { name: /ciano/i }).click();

  await expect(page.locator('html')).toHaveAttribute('data-modo', 'light');
  await expect(page.locator('html')).toHaveAttribute('data-skin', 'ciano');

  await page.reload();
  await expect(page.locator('html')).toHaveAttribute('data-modo', 'light');
  await expect(page.locator('html')).toHaveAttribute('data-skin', 'ciano');
});

test('mantém o modo claro na empresa e na área do aluno', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: /ativar modo claro/i }).click();

  await page.goto('/empresa/gerar');
  await expect(page.locator('html')).toHaveAttribute('data-modo', 'light');
  await expect(page.locator('.logo-para-modo-claro').first()).toBeVisible();

  await page.goto('/aluno');
  await expect(page.locator('html')).toHaveAttribute('data-modo', 'light');
  await expect(page.locator('.logo-para-modo-claro').first()).toBeVisible();
});
