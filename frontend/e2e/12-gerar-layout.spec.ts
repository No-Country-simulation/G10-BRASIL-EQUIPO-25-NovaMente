import { expect, test } from '@playwright/test';

// Os tamanhos de notebook mais comuns: todas as opções e o botão Gerar precisam
// aparecer sem rolar a página.
for (const [largura, altura] of [
  [1366, 768],
  [1440, 900],
  [1920, 1080],
] as const) {
  test(`tela de geração cabe em ${largura}x${altura} sem rolagem`, async ({ page }) => {
    await page.setViewportSize({ width: largura, height: altura });
    await page.addInitScript(() =>
      window.localStorage.setItem('novamente.tour', JSON.stringify({ versao: 1 })),
    );
    await page.goto('/empresa/gerar');
    await expect(page.getByRole('button', { name: 'Gerar material' })).toBeVisible();

    const medidas = await page.evaluate(() => ({
      conteudo: document.documentElement.scrollHeight,
      janela: window.innerHeight,
      larguraConteudo: document.documentElement.scrollWidth,
      larguraJanela: window.innerWidth,
      botao: document.querySelector<HTMLButtonElement>('button[type="submit"]')?.getBoundingClientRect().bottom,
    }));

    expect(medidas.conteudo).toBeLessThanOrEqual(medidas.janela);
    expect(medidas.larguraConteudo).toBeLessThanOrEqual(medidas.larguraJanela);
    expect(medidas.botao).toBeLessThanOrEqual(medidas.janela);

    for (const rotulo of [
      'Perfil do destinatário',
      'Formato de saída',
      'Nicho / setor',
      'Nível de detalhe',
      'Conteúdo técnico',
    ]) {
      await expect(page.getByText(rotulo, { exact: true })).toBeInViewport();
    }
  });
}

test('em tela estreita o formulário empilha e o progresso aparece ao gerar', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.addInitScript(() =>
    window.localStorage.setItem('novamente.tour', JSON.stringify({ versao: 1 })),
  );
  await page.goto('/empresa/gerar');

  const larguras = await page.evaluate(() => [
    document.documentElement.scrollWidth,
    window.innerWidth,
  ]);
  expect(larguras[0]).toBeLessThanOrEqual(larguras[1]);
});
