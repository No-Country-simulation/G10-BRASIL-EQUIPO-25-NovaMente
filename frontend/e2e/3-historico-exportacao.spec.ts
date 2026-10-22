import { expect, test } from '@playwright/test';

test('histórico reabre pacote, baixa JSON e desabilita CSV para não-Flashcards', async ({ page }) => {
  await page.goto('/');
  await page.getByLabel(/título do documento/i).fill('Manual de operações VCN');
  await page.getByLabel(/conteúdo técnico/i).fill('A Virtual Cloud Network é uma rede privada. '.repeat(8));
  // O input é sr-only dentro do label; o alvo real de clique é o rótulo visível.
  await page
    .getByRole('group', { name: /formato de saída/i })
    .getByText('Tutorial', { exact: true })
    .click();
  await expect(page.getByRole('radio', { name: /^tutorial/i })).toBeChecked();
  await page.getByRole('button', { name: /gerar material/i }).click();

  await expect(page).toHaveURL(/\/resultado\//, { timeout: 30_000 });

  await page.getByRole('link', { name: 'Histórico' }).click();
  await expect(page.getByText('Manual de operações VCN').first()).toBeVisible();
  await page.getByText('Manual de operações VCN').first().click();

  await expect(page).toHaveURL(/\/resultado\//);
  const download = page.waitForEvent('download');
  await page.getByRole('button', { name: /baixar json/i }).click();
  expect((await download).suggestedFilename()).toMatch(/\.json$/);

  await page.getByRole('button', { name: 'Exportar' }).click();
  await expect(page.getByRole('menuitem', { name: /csv/i })).toHaveAttribute('aria-disabled', 'true');
});
