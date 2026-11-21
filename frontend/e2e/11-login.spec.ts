import { expect, test, type Page } from '@playwright/test';

// Liga o login no mock (desligado por padrão para não alterar os outros fluxos).
async function ligarLogin(page: Page) {
  await page.addInitScript(() => {
    if (!window.localStorage.getItem('novamente.mock.auth')) {
      window.localStorage.setItem('novamente.mock.auth', '1');
    }
  });
}

test('sem login ligado, a landing leva direto para a área da empresa', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('link', { name: /área da empresa/i }).click();
  await expect(page).toHaveURL(/\/empresa\/gerar/);
});

test('empresa entra com senha e depois com o código do e-mail', async ({ page }) => {
  await ligarLogin(page);
  await page.goto('/empresa/materiais');

  await expect(page).toHaveURL(/\/entrar\?perfil=empresa&proximo=%2Fempresa%2Fmateriais/);
  await expect(page.getByText(/use um e-mail válido/i)).toBeVisible();
  await expect(page.getByText(/mínimo de 8 caracteres/i)).toBeVisible();

  await page.getByLabel('E-mail da empresa').fill('empresa@demo.com');
  await page.getByLabel('Senha', { exact: true }).fill('Errada@123');
  await page.getByRole('button', { name: 'Continuar' }).click();
  await expect(page.getByText('E-mail ou senha incorretos.')).toBeVisible();

  await page.getByLabel('Senha', { exact: true }).fill('Demo@1234');
  await page.getByRole('button', { name: 'Continuar' }).click();

  await expect(page.getByText(/enviamos um código de 6 dígitos para empresa@demo.com/i)).toBeVisible();
  await expect(page.getByText(/confira a caixa de spam/i)).toBeVisible();

  await page.getByLabel('Código de 6 dígitos').fill('000000');
  await page.getByRole('button', { name: 'Verificar e entrar' }).click();
  await expect(page.getByText('Código inválido ou vencido.')).toBeVisible();

  await page.getByLabel('Código de 6 dígitos').fill('123456');
  await page.getByRole('button', { name: 'Verificar e entrar' }).click();
  await expect(page).toHaveURL(/\/empresa\/materiais/);
  await expect(page.getByTestId('menu-sessao')).toBeVisible();

  await page.getByRole('button', { name: 'Sair' }).click();
  await expect(page).toHaveURL(/\/entrar\?perfil=empresa/);

  await page.goto('/empresa/gerar');
  await expect(page).toHaveURL(/\/entrar\?perfil=empresa/);
});

test('aluno com senha entra com e-mail, senha e código; sair encerra a sessão', async ({ page }) => {
  await ligarLogin(page);
  await page.goto('/entrar?perfil=aluno');

  await page.getByLabel('Seu e-mail').fill('ana.silva@exemplo.com');
  await page.getByLabel('Senha', { exact: true }).fill('Aluno@1234');
  await page.getByRole('button', { name: 'Continuar' }).click();

  await page.getByLabel('Código de 6 dígitos').fill('123456');
  await page.getByRole('button', { name: 'Verificar e entrar' }).click();

  await expect(page).toHaveURL(/\/aluno$/);
  await expect(page.getByTestId('menu-sessao')).toContainText('Ana');
  await expect(page.getByRole('heading', { name: /quem está estudando/i })).toHaveCount(0);

  await page.getByRole('button', { name: 'Sair' }).click();
  await page.goto('/aluno');
  await expect(page).toHaveURL(/\/entrar\?perfil=aluno/);
});

test('primeiro acesso do aluno: confirma o e-mail, cria a senha e depois entra com ela', async ({
  page,
}) => {
  await ligarLogin(page);
  await page.goto('/entrar?perfil=aluno');

  // Sem senha criada, o login comum não funciona.
  await page.getByLabel('Seu e-mail').fill('bruno.carvalho@exemplo.com');
  await page.getByLabel('Senha', { exact: true }).fill('Aluno@1234');
  await page.getByRole('button', { name: 'Continuar' }).click();
  await expect(page.getByText('E-mail ou senha incorretos.')).toBeVisible();

  await page.getByRole('button', { name: /primeiro acesso ou esqueci a senha/i }).click();
  await page.getByLabel('Seu e-mail').fill('bruno.carvalho@exemplo.com');
  await page.getByRole('button', { name: 'Enviar código' }).click();

  const botao = page.getByRole('button', { name: 'Criar senha e entrar' });
  await page.getByLabel('Código de 6 dígitos').fill('123456');
  await page.getByLabel('Crie sua senha').fill('fraca');
  await page.getByLabel('Repita a senha').fill('fraca');
  await expect(botao).toBeDisabled();

  await page.getByLabel('Crie sua senha').fill('Bruno@2026x');
  await expect(page.getByText('Uma letra maiúscula').locator('..')).toContainText('atendido');
  await page.getByLabel('Repita a senha').fill('Bruno@2026x');
  await botao.click();

  await expect(page).toHaveURL(/\/aluno$/);
  await expect(page.getByTestId('menu-sessao')).toContainText('Bruno');

  // Nos próximos acessos, e-mail + senha + código.
  await page.getByRole('button', { name: 'Sair' }).click();
  await page.goto('/entrar?perfil=aluno');
  await page.getByLabel('Seu e-mail').fill('bruno.carvalho@exemplo.com');
  await page.getByLabel('Senha', { exact: true }).fill('Bruno@2026x');
  await page.getByRole('button', { name: 'Continuar' }).click();
  await page.getByLabel('Código de 6 dígitos').fill('123456');
  await page.getByRole('button', { name: 'Verificar e entrar' }).click();
  await expect(page).toHaveURL(/\/aluno$/);
});

test('demonstração entra sem cadastro e aluno não acessa a área da empresa', async ({ page }) => {
  await ligarLogin(page);
  await page.goto('/entrar?perfil=aluno');

  await page.getByRole('button', { name: 'Entrar como aluno de demonstração' }).click();
  await expect(page).toHaveURL(/\/aluno$/);
  await expect(page.getByText('Demonstração')).toBeVisible();

  await page.goto('/empresa/gerar');
  await expect(page.getByRole('heading', { name: 'Esta área é da empresa' })).toBeVisible();
});

test('depois do login, o tour é a primeira coisa na tela de geração e abre uma vez por conta', async ({
  page,
}) => {
  await ligarLogin(page);
  await page.goto('/entrar?perfil=empresa');

  await page.getByLabel('E-mail da empresa').fill('empresa@demo.com');
  await page.getByLabel('Senha', { exact: true }).fill('Demo@1234');
  await page.getByRole('button', { name: 'Continuar' }).click();
  await page.getByLabel('Código de 6 dígitos').fill('123456');
  await page.getByRole('button', { name: 'Verificar e entrar' }).click();

  await expect(page).toHaveURL(/\/empresa\/gerar$/);
  const dialogo = page.getByRole('dialog');
  await expect(dialogo).toBeVisible({ timeout: 8_000 });
  await expect(dialogo).toContainText('Área da empresa');
  // O tour da empresa não leva para a área do aluno.
  await expect(dialogo).toContainText('1 de 5');
  await page.getByRole('button', { name: 'Pular tour' }).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);

  await page.reload();
  await page.waitForTimeout(1_200);
  await expect(page.getByRole('dialog')).toHaveCount(0);
});

test('a página de entrada nunca abre o tour sozinha', async ({ page }) => {
  await ligarLogin(page);
  await page.goto('/entrar');
  await page.waitForTimeout(1_200);
  await expect(page.getByRole('dialog')).toHaveCount(0);
});
