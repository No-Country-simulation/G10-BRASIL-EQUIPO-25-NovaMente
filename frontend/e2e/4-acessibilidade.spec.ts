import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';

const ROTAS = [
  { rota: '/', titulo: /gerar material didático/i },
  { rota: '/historico', titulo: 'Histórico' },
  { rota: '/resultado/01JAVCNFLCARD00000000001', titulo: /dominando redes na nuvem/i },
];

for (const { rota, titulo } of ROTAS) {
  test(`sem violação crítica de acessibilidade em ${rota}`, async ({ page }) => {
    await page.goto(rota);
    // A página só ganha conteúdo depois do worker do MSW e da query do pacote.
    await expect(page.getByRole('heading', { name: titulo })).toBeVisible();
    await page.waitForLoadState('networkidle');

    const resultado = await new AxeBuilder({ page }).analyze();
    const criticas = resultado.violations.filter((v) => v.impact === 'critical');
    expect(criticas, JSON.stringify(criticas, null, 2)).toEqual([]);
  });
}
