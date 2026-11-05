import { expect, test, type Page } from '@playwright/test';

const LARGURAS = [375, 320];

async function medir(page: Page) {
  return page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
  }));
}

async function semRolagemHorizontal(page: Page, tela: string) {
  const { scrollWidth, clientWidth } = await medir(page);
  expect.soft(scrollWidth, `${tela} com rolagem horizontal`).toBeLessThanOrEqual(clientWidth);
}

async function gerarPorCenario(page: Page, cenario: RegExp) {
  await page.goto('/');
  await page.getByRole('button', { name: cenario }).click();
  await expect(page).toHaveURL(/\/resultado\/01J/, { timeout: 30_000 });
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
}

async function gerarTutorial(page: Page) {
  await page.goto('/');
  await page.getByLabel(/título do documento/i).fill('Manual de operações VCN');
  await page.getByLabel(/conteúdo técnico/i).fill('A Virtual Cloud Network é uma rede privada. '.repeat(8));
  // Os inputs de rádio são sr-only dentro do label; o alvo real de clique é o rótulo visível.
  await page
    .getByRole('group', { name: /formato de saída/i })
    .getByText('Tutorial', { exact: true })
    .click();
  await expect(page.getByRole('radio', { name: /^tutorial/i })).toBeChecked();
  await page.getByRole('button', { name: /gerar material/i }).click();
  await expect(page).toHaveURL(/\/resultado\/01J/, { timeout: 30_000 });
  await expect(
    page.getByRole('heading', { name: 'Desenhando uma VCN pronta para produção' }),
  ).toBeVisible();
}

for (const largura of LARGURAS) {
  test(`sem rolagem horizontal em ${largura}px`, async ({ page }) => {
    await page.setViewportSize({ width: largura, height: 800 });

    await page.goto('/');
    await expect(page.getByRole('button', { name: /gerar material/i })).toBeVisible();
    await semRolagemHorizontal(page, 'gerar');

    await gerarPorCenario(page, /iniciante \+ flashcards/i);
    await semRolagemHorizontal(page, 'resultado flashcards');

    await gerarPorCenario(page, /desenvolvedor \+ quiz/i);
    await semRolagemHorizontal(page, 'resultado quiz');

    await gerarTutorial(page);
    await semRolagemHorizontal(page, 'resultado tutorial');

    // Navegação pelo cabeçalho (sem recarregar), para o mock manter os pacotes gerados.
    await page.getByRole('link', { name: 'Histórico' }).click();
    await expect(page).toHaveURL(/\/historico/);
    await expect(page.getByRole('link', { name: /manual de operações vcn/i }).first()).toBeVisible();
    await semRolagemHorizontal(page, 'histórico');
  });
}
