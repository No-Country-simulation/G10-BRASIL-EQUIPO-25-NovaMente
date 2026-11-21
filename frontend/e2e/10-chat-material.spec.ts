import { expect, test } from '@playwright/test';

const ALUNO_ANA = { aluno_id: '01JALUNO000000000000000001', nome: 'Ana Beatriz Silva' };
const QUIZ = '01JAVCNQUIZ000000000002';
const CARDS = '01JAVCNFLCARD00000000001';

test('aluno pergunta ao material, vê a fonte e troca o modelo', async ({ page }) => {
  await page.goto('/aluno');
  await page.evaluate((dados) => {
    window.localStorage.setItem('novamente.aluno', JSON.stringify(dados));
  }, ALUNO_ANA);
  await page.goto(`/aluno/materiais/${QUIZ}`);

  await expect(
    page.getByRole('heading', { name: /tire dúvidas sobre este material/i }),
  ).toBeVisible();

  await page.getByLabel('Modelo').selectOption('nvidia/nemotron-3.5-bolt-e4b');
  await page.getByLabel('Sua pergunta').fill('Para que serve o NAT Gateway?');
  await page.getByRole('button', { name: 'Enviar' }).click();

  const historico = page.getByRole('log', { name: /conversa com o assistente/i });
  await expect(historico.getByText(/segundo o material/i)).toBeVisible();
  await expect(historico.getByText('1 fonte')).toBeVisible();
  await expect(page.getByLabel('Sua pergunta')).toHaveValue('');

  await page.getByLabel('Sua pergunta').fill('Quem descobriu o Brasil?');
  await page.getByLabel('Sua pergunta').press('Enter');
  await expect(historico.getByText('Não encontrei isso no material.')).toBeVisible();
  await expect(historico.getByText('Sem base no material')).toBeVisible();
});

test('empresa pergunta ao material no resultado, inclusive em rascunho', async ({ page }) => {
  await page.goto(`/empresa/resultado/${CARDS}`);

  await page.getByLabel('Sua pergunta').fill('O que é uma rede privada?');
  await page.getByRole('button', { name: 'Enviar' }).click();

  await expect(
    page.getByRole('log', { name: /conversa com o assistente/i }).getByText(/segundo o material/i),
  ).toBeVisible();
});
