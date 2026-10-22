import { expect, test } from '@playwright/test';

test('cenário Iniciante + Flashcards gera, vira o cartão e exporta Markdown', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: /iniciante \+ flashcards/i }).click();

  await expect(page).toHaveURL(/\/resultado\/01J/, { timeout: 30_000 });
  await expect(page.getByRole('heading', { name: /dominando redes na nuvem/i })).toBeVisible();
  await expect(page.getByText('O que é uma VCN na Oracle Cloud?')).toBeVisible();

  await page.getByRole('button', { name: /mostrar verso/i }).click();
  await expect(page.getByRole('button', { name: /mostrar frente/i })).toHaveAttribute(
    'aria-pressed',
    'true',
  );

  const download = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Exportar' }).click();
  await page.getByRole('menuitem', { name: 'Markdown' }).click();
  expect((await download).suggestedFilename()).toMatch(/^novamente-.*\.md$/);

  // Flashcards têm CSV: o item precisa continuar habilitado.
  await page.getByRole('button', { name: 'Exportar' }).click();
  const csv = page.getByRole('menuitem', { name: /csv/i });
  await expect(csv).toBeVisible();
  await expect(csv).not.toHaveAttribute('aria-disabled', 'true');
});
