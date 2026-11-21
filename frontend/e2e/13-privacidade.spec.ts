import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';

// Aqui o usuário é novo: sem escolha de cookies registrada.
test.use({ storageState: { cookies: [], origins: [] } });

const banner = (page: Page) => page.getByTestId('banner-cookies');
const tour = (page: Page) => page.locator('.driver-popover');

async function lerArmazenamento(page: Page, chave: string) {
  return page.evaluate(
    (k) => ({ local: window.localStorage.getItem(k), sessao: window.sessionStorage.getItem(k) }),
    chave,
  );
}

test('novo usuário vê o aviso, recusa as preferências e ele não volta', async ({ page }) => {
  await page.goto('/');
  await expect(banner(page)).toBeVisible();
  await expect(banner(page)).toContainText('Não usamos cookies de publicidade');

  await page.getByRole('button', { name: 'Somente necessários' }).click();
  await expect(banner(page)).toHaveCount(0);

  const escolha = JSON.parse((await lerArmazenamento(page, 'novamente.consentimento')).local!);
  expect(escolha).toMatchObject({ preferencias: false, versao: 1 });

  // O tema escolhido vale só na sessão: nada vai para o armazenamento que dura.
  await page.getByRole('button', { name: /ciano/i }).first().click();
  await expect(page.locator('html')).toHaveAttribute('data-skin', 'ciano');
  const tema = await lerArmazenamento(page, 'novamente.skin');
  expect(tema.local).toBeNull();
  expect(tema.sessao).not.toBeNull();

  await page.reload();
  await expect(page.locator('html')).toHaveAttribute('data-skin', 'ciano');
  await page.waitForTimeout(500);
  await expect(banner(page)).toHaveCount(0);
});

test('aceitar as preferências guarda o tema entre visitas', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: 'Aceitar preferências' }).click();
  await expect(banner(page)).toHaveCount(0);

  await page.getByRole('button', { name: /ciano/i }).first().click();
  const tema = await lerArmazenamento(page, 'novamente.skin');
  expect(tema.local).not.toBeNull();
  expect(tema.sessao).toBeNull();

  await page.reload();
  await expect(page.locator('html')).toHaveAttribute('data-skin', 'ciano');
  await expect(banner(page)).toHaveCount(0);
});

test('o tour só abre depois da escolha de cookies, uma vez, e pode ser pulado', async ({ page }) => {
  await page.goto('/empresa/gerar');
  await expect(banner(page)).toBeVisible();
  await page.waitForTimeout(1_200);
  await expect(tour(page)).toHaveCount(0);

  await page.getByRole('button', { name: 'Aceitar preferências' }).click();
  await expect(tour(page)).toBeVisible({ timeout: 5_000 });
  await expect(tour(page)).toContainText('1 de 5');

  await page.getByRole('button', { name: 'Pular tour' }).click();
  await expect(tour(page)).toHaveCount(0);

  // Quem já viu (ou pulou) não vê de novo sozinho, nem o aviso.
  await page.reload();
  await page.waitForTimeout(1_200);
  await expect(tour(page)).toHaveCount(0);
  await expect(banner(page)).toHaveCount(0);

  // Para rever, o botão "Ver tour" continua ali.
  await page.getByRole('button', { name: 'Ver tour' }).click();
  await expect(tour(page)).toBeVisible({ timeout: 5_000 });
});

test('recusando as preferências, o tour já visto não repete na mesma sessão', async ({ page }) => {
  await page.goto('/empresa/gerar');
  await page.getByRole('button', { name: 'Somente necessários' }).click();
  await expect(tour(page)).toBeVisible({ timeout: 5_000 });
  await page.getByRole('button', { name: 'Pular tour' }).click();

  const registro = await lerArmazenamento(page, 'novamente.tour');
  expect(registro.local).toBeNull();
  expect(registro.sessao).not.toBeNull();

  await page.reload();
  await page.waitForTimeout(1_200);
  await expect(tour(page)).toHaveCount(0);
});

test('o rodapé reabre o aviso e revogar apaga as preferências guardadas', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: 'Aceitar preferências' }).click();
  await page.getByRole('button', { name: /ciano/i }).first().click();
  expect((await lerArmazenamento(page, 'novamente.skin')).local).not.toBeNull();

  await page.getByRole('button', { name: 'Preferências de cookies' }).click();
  await expect(banner(page)).toBeVisible();
  const interruptor = page.getByRole('switch', { name: 'Preferências' });
  await expect(interruptor).toHaveAttribute('aria-checked', 'true');

  await interruptor.click();
  await page.getByRole('button', { name: 'Salvar minhas escolhas' }).click();
  await expect(banner(page)).toHaveCount(0);

  const escolha = JSON.parse((await lerArmazenamento(page, 'novamente.consentimento')).local!);
  expect(escolha.preferencias).toBe(false);
  expect((await lerArmazenamento(page, 'novamente.skin')).local).toBeNull();
});

test('a política abre pelo aviso e pelo rodapé e traz cookies, direitos e LGPD', async ({ page }) => {
  await page.goto('/');
  await banner(page).getByRole('link', { name: 'Política de Privacidade e Cookies' }).click();
  await expect(page).toHaveURL(/\/privacidade$/);
  await expect(
    page.getByRole('heading', { level: 1, name: 'Política de Privacidade e Cookies' }),
  ).toBeVisible();
  await expect(page.getByRole('heading', { level: 3, name: 'nm_sessao' })).toBeVisible();
  await expect(page.getByText('Revogação do consentimento')).toBeVisible();
  await expect(page.getByRole('link', { name: /Lei nº 13\.709\/2018/ })).toBeVisible();

  // O sumário leva à seção.
  await page.getByRole('link', { name: '8. Seus direitos' }).click();
  await expect(page).toHaveURL(/#direitos$/);

  // Do rodapé da landing, também.
  await page.goto('/');
  await page.getByRole('button', { name: 'Somente necessários' }).click();
  await page.getByRole('link', { name: 'Privacidade e cookies' }).click();
  await expect(page).toHaveURL(/\/privacidade$/);
});

test('em tela de celular o aviso cabe na tela e não cria rolagem horizontal', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 700 });
  await page.goto('/');
  await expect(banner(page)).toBeVisible();

  const caixa = await banner(page).boundingBox();
  expect(caixa!.x).toBeGreaterThanOrEqual(0);
  expect(caixa!.x + caixa!.width).toBeLessThanOrEqual(375);
  expect(caixa!.y + caixa!.height).toBeLessThanOrEqual(700);
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
  ).toBe(true);

  await page.getByRole('button', { name: 'Personalizar' }).click();
  await expect(page.getByRole('switch', { name: 'Preferências' })).toBeVisible();
  await page.getByRole('button', { name: 'Salvar minhas escolhas' }).click();
  await expect(banner(page)).toHaveCount(0);
});

const SKINS = ['violeta', 'ciano', 'neural'] as const;
const MODOS = ['dark', 'light'] as const;

for (const skin of SKINS) {
  for (const modo of MODOS) {
    test(`sem violação crítica ou séria com o aviso aberto e a política (${skin}, ${modo})`, async ({
      page,
    }) => {
      await page.addInitScript(
        ({ skinValor, modoValor }) => {
          window.sessionStorage.setItem(
            'novamente.skin',
            JSON.stringify({ state: { skin: skinValor, modo: modoValor }, version: 2 }),
          );
        },
        { skinValor: skin, modoValor: modo },
      );
      await page.goto('/privacidade');
      await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
      await page.getByRole('button', { name: 'Personalizar' }).click();
      await expect(page.getByRole('switch', { name: 'Preferências' })).toBeVisible();
      await page.waitForLoadState('networkidle');

      const resultado = await new AxeBuilder({ page }).analyze();
      const graves = resultado.violations.filter(
        (v) => v.impact === 'critical' || v.impact === 'serious',
      );
      expect(graves, JSON.stringify(graves, null, 2)).toEqual([]);
    });
  }
}
