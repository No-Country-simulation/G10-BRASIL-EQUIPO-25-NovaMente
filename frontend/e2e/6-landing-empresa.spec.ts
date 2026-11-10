import { expect, test } from '@playwright/test';

test.describe('landing e área da empresa', () => {
  test.beforeEach(async ({ page }) => {
    // O tour não deve cobrir a tela durante o fluxo de gestão.
    await page.addInitScript(() => {
      window.localStorage.setItem(
        'novamente.tour',
        JSON.stringify({ versao: 1, concluido_em: new Date().toISOString() }),
      );
    });
  });

  test('landing apresenta a proposta e leva à geração; empresa publica, vincula e exclui', async ({
    page,
  }) => {
    await page.goto('/');

    await expect(page.getByRole('heading', { level: 1 })).toContainText(/material didático/i);
    await expect(page.getByRole('link', { name: /área da empresa/i }).first()).toHaveAttribute(
      'href',
      '/empresa/gerar',
    );
    await expect(page.getByRole('link', { name: /sou aluno/i })).toHaveAttribute(
      'href',
      '/aluno',
    );
    for (const formato of [/flashcards/i, /quiz interativo/i, /tutorial/i, /resumo executivo/i]) {
      await expect(page.getByText(formato).first()).toBeVisible();
    }

    await page.getByRole('link', { name: /área da empresa/i }).first().click();
    await expect(page).toHaveURL(/\/empresa\/gerar$/);
    await expect(page.getByRole('heading', { name: /gerar material didático/i })).toBeVisible();

    await page.getByRole('button', { name: /iniciante \+ flashcards/i }).click();
    await expect(page).toHaveURL(/\/empresa\/resultado\/01J/, { timeout: 30_000 });
    await expect(
      page.getByRole('heading', { name: /dominando redes na nuvem/i }),
    ).toBeVisible();

    const idGerado = new URL(page.url()).pathname.split('/').pop();
    expect(idGerado).toBeTruthy();
    const hrefGerado = `/empresa/resultado/${idGerado}`;

    await page.getByRole('link', { name: 'Materiais', exact: true }).first().click();
    await expect(page).toHaveURL(/\/empresa\/materiais$/);

    const cartao = page
      .locator('article')
      .filter({ has: page.locator(`a[href="${hrefGerado}"]`) });
    await expect(cartao).toHaveCount(1);

    await cartao.getByRole('button', { name: 'Publicar', exact: true }).click();
    await expect(page.getByText('Material publicado.')).toBeVisible();

    await cartao.getByRole('button', { name: 'Editar', exact: true }).click();
    const dialogoMaterial = page.getByRole('dialog', { name: /editar material/i });
    await dialogoMaterial.getByLabel(/título do material/i).fill('Material E2E publicado');
    await dialogoMaterial.getByRole('button', { name: 'Salvar' }).click();
    await expect(page.getByText('Material atualizado.')).toBeVisible();
    await expect(cartao.getByText('Material E2E publicado')).toBeVisible();

    await page.getByRole('link', { name: 'Alunos', exact: true }).first().click();
    await expect(page).toHaveURL(/\/empresa\/alunos$/);

    await page.getByRole('button', { name: /novo aluno/i }).click();
    const dialogoAluno = page.getByRole('dialog', { name: /novo aluno/i });
    await dialogoAluno.getByLabel('Nome', { exact: true }).fill('Aluno E2E');
    await dialogoAluno.getByLabel('E-mail', { exact: true }).fill('aluno.e2e@exemplo.com');
    await dialogoAluno.getByRole('button', { name: 'Salvar' }).click();
    await expect(page.getByText('Aluno cadastrado.')).toBeVisible();

    const linhaAluno = page.getByRole('row').filter({ hasText: 'Aluno E2E' });
    await expect(linhaAluno).toBeVisible();
    await linhaAluno.getByRole('link', { name: 'Materiais' }).click();
    await expect(page).toHaveURL(/\/empresa\/alunos\/01J/);
    await expect(page.getByRole('heading', { name: 'Aluno E2E' })).toBeVisible();

    await page.getByRole('checkbox', { name: /selecionar material e2e publicado/i }).check();
    await page.getByRole('button', { name: /salvar vínculos/i }).click();
    await expect(page.getByText('Vínculos atualizados.')).toBeVisible();

    await page.getByRole('link', { name: 'Materiais', exact: true }).first().click();
    await expect(page).toHaveURL(/\/empresa\/materiais$/);

    const cartaoFinal = page
      .locator('article')
      .filter({ has: page.locator(`a[href="${hrefGerado}"]`) });
    await expect(cartaoFinal).toHaveCount(1);
    await cartaoFinal.getByRole('button', { name: 'Excluir', exact: true }).click();

    const dialogoExclusao = page.getByRole('dialog', { name: /excluir material/i });
    await dialogoExclusao.getByRole('button', { name: /confirmar e excluir/i }).click();
    await expect(page.getByText('Material excluído.')).toBeVisible();
    await expect(page.getByText('Material E2E publicado')).toHaveCount(0);
  });

  test('rotas antigas redirecionam permanentemente para a área da empresa', async ({
    page,
  }) => {
    const historico = await page.request.get('/historico', { maxRedirects: 0 });
    expect(historico.status()).toBe(308);
    expect(historico.headers()['location']).toMatch(/\/empresa\/historico$/);

    await page.goto('/historico');
    await expect(page).toHaveURL(/\/empresa\/historico$/);
    await expect(page.getByRole('heading', { name: 'Histórico' })).toBeVisible();

    const resultado = await page.request.get('/resultado/01JAVCNFLCARD00000000001', {
      maxRedirects: 0,
    });
    expect(resultado.status()).toBe(308);
    expect(resultado.headers()['location']).toMatch(
      /\/empresa\/resultado\/01JAVCNFLCARD00000000001$/,
    );

    await page.goto('/resultado/01JAVCNFLCARD00000000001');
    await expect(page).toHaveURL(/\/empresa\/resultado\/01JAVCNFLCARD00000000001$/);
    await expect(
      page.getByRole('heading', { name: /dominando redes na nuvem/i }),
    ).toBeVisible();
  });
});
