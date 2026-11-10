import { expect, test, type Page } from '@playwright/test';

const ALUNO_ANA = { aluno_id: '01JALUNO000000000000000001', nome: 'Ana Beatriz Silva' };
const ALUNO_BRUNO = { aluno_id: '01JALUNO000000000000000002', nome: 'Bruno Carvalho' };

async function definirAluno(page: Page, aluno: typeof ALUNO_ANA) {
  await page.evaluate((dados) => {
    window.localStorage.setItem('novamente.aluno', JSON.stringify(dados));
  }, aluno);
}

test('aluno identifica sem senha, estuda o material liberado e trata indisponíveis', async ({
  page,
}) => {
  await page.goto('/aluno');

  await expect(page.getByRole('heading', { name: /quem está estudando/i })).toBeVisible();
  await expect(page.getByText('Identificação sem senha nesta versão.')).toBeVisible();
  await page.getByRole('button', { name: /selecionar ana beatriz silva/i }).click();
  await page.getByRole('button', { name: 'Entrar', exact: true }).click();

  await expect(
    page.getByRole('heading', { name: /olá, ana beatriz silva/i }),
  ).toBeVisible();
  // Rascunho não aparece no catálogo do aluno.
  await expect(page.getByText('Dominando Redes na Nuvem (VCN) do Zero')).toHaveCount(0);

  const cartaoQuiz = page.locator('article').filter({ hasText: /vcn na prática/i });
  await expect(cartaoQuiz).toBeVisible();
  await cartaoQuiz.getByRole('link', { name: 'Estudar' }).click();

  await expect(page).toHaveURL(/\/aluno\/materiais\/01JAVCNQUIZ/);
  await expect(page.getByRole('heading', { name: /vcn na prática/i })).toBeVisible();

  for (let i = 0; i < 6; i += 1) {
    await page.getByRole('radio').first().check();
    await page.getByRole('button', { name: 'Confirmar' }).click();
    await page.getByRole('button', { name: 'Próxima' }).click();
  }
  await expect(page.getByRole('heading', { name: 'Placar' })).toBeVisible();

  // Rascunho por URL direta não é revelado.
  await page.goto('/aluno/materiais/01JAVCNFLCARD00000000001');
  await expect(page.getByText('Este material não está disponível.')).toBeVisible();

  // Material publicado, mas não vinculado ao aluno, também não é revelado.
  await definirAluno(page, ALUNO_BRUNO);
  await page.goto('/aluno/materiais/01JAVCNQUIZ000000000002');
  await expect(page.getByText('Este material não está disponível.')).toBeVisible();

  // Trocar aluno limpa a sessão e volta à identificação.
  await definirAluno(page, ALUNO_ANA);
  await page.goto('/aluno');
  await page.getByRole('link', { name: 'Trocar aluno' }).click();
  await expect(page.getByRole('heading', { name: /quem está estudando/i })).toBeVisible();
  expect(await page.evaluate(() => window.localStorage.getItem('novamente.aluno'))).toBeNull();
});
