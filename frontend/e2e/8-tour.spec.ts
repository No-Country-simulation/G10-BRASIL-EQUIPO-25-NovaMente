import { expect, test } from '@playwright/test';

test('tour auto-inicia uma vez, reinicia pelo botão e força o roteiro completo', async ({
  page,
}) => {
  await page.goto('/empresa/gerar');

  const dialogo = page.getByRole('dialog');
  await expect(dialogo).toBeVisible({ timeout: 5_000 });
  await expect(dialogo).toContainText('Área da empresa');
  await expect(dialogo).toContainText('1 de 6');

  await page.getByRole('button', { name: 'Pular tour' }).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);

  // Recarregar não auto-inicia de novo.
  await page.reload();
  await page.waitForTimeout(900);
  await expect(page.getByRole('dialog')).toHaveCount(0);

  // "Ver tour" reinicia mesmo com a conclusão registrada.
  await page.getByRole('button', { name: 'Ver tour' }).click();
  await expect(page.getByRole('dialog')).toBeVisible({ timeout: 5_000 });
  await expect(page.getByRole('dialog')).toContainText('Área da empresa');
  await page.getByRole('button', { name: 'Pular tour' }).click();

  // ?tour=1 força o roteiro completo a partir da área do aluno, sem entrar em /empresa.
  await page.goto('/aluno?tour=1');
  await expect(page.getByRole('dialog')).toBeVisible({ timeout: 5_000 });
  await expect(page.getByRole('dialog')).toContainText('Bem-vindo ao NovaMente');
  await expect(page).toHaveURL(/\/$/);
  await page.getByRole('button', { name: 'Pular tour' }).click();
});
