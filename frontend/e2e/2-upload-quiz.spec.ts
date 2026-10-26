import { expect, test } from '@playwright/test';

test('upload de Markdown gera quiz, responde tudo e mostra placar', async ({ page }) => {
  await page.goto('/');
  await page.getByLabel(/título do documento/i).fill('Manual de VCN para devs');
  await page.getByRole('tab', { name: /enviar arquivo/i }).click();
  await page.setInputFiles('input[type="file"]', {
    name: 'vcn.md',
    mimeType: 'text/markdown',
    buffer: Buffer.from('# VCN\n\nA VCN é uma rede privada e personalizável na OCI.'),
  });
  // O input é sr-only dentro do label; o alvo real de clique é o rótulo visível.
  await page
    .getByRole('group', { name: /formato de saída/i })
    .getByText('Quiz interativo', { exact: true })
    .click();
  await expect(page.getByRole('radio', { name: /quiz interativo/i })).toBeChecked();
  await page.getByRole('button', { name: /gerar material/i }).click();

  await expect(page).toHaveURL(/\/resultado\//, { timeout: 30_000 });
  await expect(page.getByRole('heading', { name: /vcn na prática/i })).toBeVisible();

  for (let i = 0; i < 6; i += 1) {
    await page.getByRole('radio').first().check();
    await page.getByRole('button', { name: 'Confirmar' }).click();
    await page.getByRole('button', { name: 'Próxima' }).click();
  }

  await expect(page.getByRole('heading', { name: 'Placar' })).toBeVisible();
  await expect(page.getByText(/\d+ \/ 6/)).toBeVisible();
});
