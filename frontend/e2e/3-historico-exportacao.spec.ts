import { expect, test } from '@playwright/test';

test('histórico reabre pacote, baixa JSON e desabilita CSV para não-Flashcards', async ({ page }) => {
  await page.goto('/');
  await page.getByLabel(/título do documento/i).fill('Manual de operações VCN');
  await page.getByLabel(/conteúdo técnico/i).fill('A Virtual Cloud Network é uma rede privada. '.repeat(8));
  // Os inputs de rádio são sr-only dentro do label; o alvo real de clique é o rótulo visível.
  await page
    .getByRole('group', { name: /perfil do destinatário/i })
    .getByText('Líder Técnico / Arquiteto', { exact: true })
    .click();
  await expect(page.getByRole('radio', { name: /líder técnico/i })).toBeChecked();
  await page
    .getByRole('group', { name: /formato de saída/i })
    .getByText('Tutorial', { exact: true })
    .click();
  await expect(page.getByRole('radio', { name: /^tutorial/i })).toBeChecked();
  await page.getByRole('button', { name: /gerar material/i }).click();

  await expect(page).toHaveURL(/\/resultado\/01J/, { timeout: 30_000 });

  await page.getByRole('link', { name: 'Histórico' }).click();
  await expect(page).toHaveURL(/\/historico/);
  // Escopo no link do card: o título do documento também aparece no header de
  // /resultado e seria encontrado antes da navegação terminar.
  const card = page.getByRole('link', { name: /manual de operações vcn/i });
  await expect(card).toBeVisible();
  await card.click();

  await expect(page).toHaveURL(/\/resultado\/01J/);
  await expect(
    page.getByRole('heading', { name: 'Desenhando uma VCN pronta para produção' }),
  ).toBeVisible();
  const download = page.waitForEvent('download');
  await page.getByRole('button', { name: /baixar json/i }).click();
  expect((await download).suggestedFilename()).toMatch(
    /^novamente-manual-de-operacoes-vcn-lider-tecnico-tutorial-[a-z0-9]{8}\.json$/,
  );

  await page.getByRole('button', { name: 'Exportar' }).click();
  await expect(page.getByRole('menuitem', { name: /csv/i })).toHaveAttribute('aria-disabled', 'true');
});
