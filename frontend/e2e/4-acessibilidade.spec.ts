import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';

interface CasoAcessibilidade {
  rota: string;
  titulo: RegExp | string;
  /** Skin aplicada antes da primeira pintura. */
  skin?: 'violeta' | 'ciano';
  /** Inclui violações `serious` (contraste AA) além das `critical`. */
  incluirSerios?: boolean;
  preparar?: (page: Page) => Promise<void>;
  espera?: (page: Page) => Promise<void>;
}

const ROTAS: CasoAcessibilidade[] = [
  {
    rota: '/',
    titulo: /material didático/i,
    incluirSerios: true,
    espera: async (page) => {
      await expect(page.getByRole('link', { name: /área da empresa/i }).first()).toBeVisible();
    },
  },
  {
    rota: '/',
    skin: 'ciano',
    titulo: /material didático/i,
    incluirSerios: true,
    espera: async (page) => {
      await expect(page.getByRole('link', { name: /área da empresa/i }).first()).toBeVisible();
    },
  },
  {
    rota: '/empresa/gerar',
    titulo: /gerar material didático/i,
    espera: async (page) => {
      await expect(page.getByRole('button', { name: /iniciante \+ flashcards/i })).toBeVisible();
    },
  },
  {
    rota: '/empresa/historico',
    titulo: 'Histórico',
    espera: async (page) => {
      // O <h1> aparece antes da query terminar; sem um item real o axe
      // analisaria o skeleton da lista.
      await page
        .getByRole('link', { name: /introdução à arquitetura de redes vcn/i })
        .first()
        .waitFor();
    },
  },
  {
    rota: '/empresa/resultado/01JAVCNFLCARD00000000001',
    titulo: /dominando redes na nuvem/i,
    espera: async (page) => {
      await page.getByRole('button', { name: /mostrar verso/i }).first().waitFor();
    },
  },
  {
    rota: '/empresa/materiais',
    titulo: 'Materiais',
    espera: async (page) => {
      await page.getByRole('link', { name: /dominando redes na nuvem/i }).first().waitFor();
    },
  },
  {
    rota: '/empresa/alunos',
    titulo: 'Alunos',
    espera: async (page) => {
      await page.getByText('Ana Beatriz Silva').waitFor();
    },
  },
  {
    rota: '/aluno',
    titulo: /quem está estudando/i,
    espera: async (page) => {
      await page.getByRole('button', { name: /selecionar ana beatriz/i }).waitFor();
    },
  },
  {
    rota: '/aluno/materiais/01JAVCNQUIZ000000000002',
    titulo: /vcn na prática/i,
    preparar: async (page) => {
      await page.addInitScript(() => {
        window.localStorage.setItem(
          'novamente.aluno',
          JSON.stringify({ aluno_id: '01JALUNO000000000000000001', nome: 'Ana Beatriz Silva' }),
        );
      });
    },
    espera: async (page) => {
      await page.getByRole('radio').first().waitFor();
    },
  },
];

for (const { rota, titulo, skin, incluirSerios, preparar, espera } of ROTAS) {
  const sufixo = skin ? ` (skin ${skin})` : '';
  const gravidade = incluirSerios ? 'crítica ou séria' : 'crítica';
  test(`sem violação ${gravidade} de acessibilidade em ${rota}${sufixo}`, async ({ page }) => {
    // O tour auto-iniciado em /empresa/gerar cobriria a tela com o overlay.
    await page.addInitScript(() => {
      window.localStorage.setItem(
        'novamente.tour',
        JSON.stringify({ versao: 1, concluido_em: new Date().toISOString() }),
      );
    });
    if (skin) {
      await page.addInitScript((valor) => {
        window.localStorage.setItem(
          'novamente.skin',
          JSON.stringify({ state: { skin: valor }, version: 1 }),
        );
      }, skin);
    }
    await preparar?.(page);

    await page.goto(rota);
    await expect(page.getByRole('heading', { name: titulo }).first()).toBeVisible();
    await espera?.(page);
    await page.waitForLoadState('networkidle');

    const resultado = await new AxeBuilder({ page }).analyze();
    const impactos = incluirSerios ? ['critical', 'serious'] : ['critical'];
    const graves = resultado.violations.filter(
      (v) => Boolean(v.impact) && impactos.includes(v.impact as string),
    );
    expect(graves, JSON.stringify(graves, null, 2)).toEqual([]);
  });
}
