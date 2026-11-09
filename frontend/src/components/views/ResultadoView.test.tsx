import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ResultadoView } from './ResultadoView';
import { M } from '@/lib/mensagens';
import { ApiProvider } from '@/services/api/ApiProvider';
import { ErroApi } from '@/services/api/erros';
import type { NovaMenteApi } from '@/services/api/NovaMenteApi';
import type { AdaptacaoPacote, MaterialResumo } from '@/types/novamente';

afterEach(() => vi.restoreAllMocks());

const pacote: AdaptacaoPacote = {
  adaptacao_id: '01JAVCNFLCARD00000000001',
  status: 'sucesso',
  criado_em: '2026-10-21T14:02:11Z',
  documento: { titulo: 'Introdução à VCN', origem: 'texto' },
  metadados: {
    perfil_aplicado: 'Iniciante',
    formato_gerado: 'Flashcards',
    nivel_detalhe_aplicado: 'Didatico',
    nicho_setor_aplicado: 'Geral',
    tempo_estimado_estudo_minutos: 5,
    conceitos_chave: ['VCN'],
  },
  conteudo_adaptado: {
    tipo: 'flashcards',
    titulo: 'Dominando Redes na Nuvem',
    introducao_contextualizada: 'Intro',
    itens: [
      { frente: 'O que é VCN?', verso: 'Rede privada.' },
      { frente: 'O que é subnet?', verso: 'Divisão da rede.' },
      { frente: 'O que é IGW?', verso: 'Porta para a internet.' },
    ],
  },
  avaliacao_qualidade: { ancoragem_fonte_score: 0.98, clareza_pedagogica: 'Alta' },
  armazenamento_oci: { bucket: 'novamente', objeto_id: 'a.json', status_upload: 'concluido' },
};

const pacoteTutorial: AdaptacaoPacote = {
  ...pacote,
  metadados: { ...pacote.metadados, formato_gerado: 'Tutorial' },
  conteudo_adaptado: {
    tipo: 'markdown',
    titulo: 'Desvendando a VCN',
    introducao_contextualizada: 'Intro',
    itens: '## Passo 1\n\nConteúdo longo o suficiente para o schema aceitar o material.',
  },
};

const material = (over: Partial<MaterialResumo> = {}): MaterialResumo => ({
  material_id: pacote.adaptacao_id,
  adaptacao_id: pacote.adaptacao_id,
  titulo: 'Dominando Redes na Nuvem (catálogo)',
  documento_titulo: 'Introdução à VCN',
  perfil: 'Iniciante',
  formato: 'Flashcards',
  nivel: 'Didatico',
  nicho: 'Geral',
  visibilidade: 'rascunho',
  tempo_estimado_estudo_minutos: 5,
  ancoragem_fonte_score: 0.98,
  status_upload: 'concluido',
  criado_em: '2026-10-21T14:02:11Z',
  atualizado_em: '2026-10-21T14:02:11Z',
  ...over,
});

function renderizar(
  sobrescrever: Partial<NovaMenteApi> = {},
  { materialAtual = material(), pacoteAtual = pacote } = {},
) {
  const detalhe = { material: materialAtual, pacote: pacoteAtual };
  const api = {
    obterMaterial: vi.fn().mockResolvedValue(detalhe),
    atualizarMaterial: vi.fn().mockResolvedValue(materialAtual),
    statusOci: vi.fn().mockResolvedValue({
      configurado: true,
      bucket: 'novamente',
      verificado_em: '2026-10-21T14:00:00Z',
    }),
    exportar: vi.fn().mockResolvedValue(new Blob(['x'])),
    baixarJson: vi.fn().mockResolvedValue(new Blob(['{}'])),
    ...sobrescrever,
  } as unknown as NovaMenteApi;
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <ApiProvider client={api}>
      <QueryClientProvider client={client}>
        <ResultadoView materialId={pacote.adaptacao_id} />
      </QueryClientProvider>
    </ApiProvider>,
  );
  return { api };
}

async function abrirMenuCsv() {
  await userEvent.click(screen.getByRole('button', { name: M.resultado.exportar }));
  return screen.findByRole('menuitem', { name: 'CSV (Anki)' });
}

describe('ResultadoView', () => {
  it('busca o material pelo id e renderiza o título do catálogo', async () => {
    const { api } = renderizar();
    expect(
      await screen.findByRole('heading', { name: 'Dominando Redes na Nuvem (catálogo)' }),
    ).toBeInTheDocument();
    expect(vi.mocked(api.obterMaterial)).toHaveBeenCalledWith(pacote.adaptacao_id);
    expect(await screen.findByText('O que é VCN?')).toBeInTheDocument();
    expect(screen.getByText('98%')).toBeInTheDocument();
  }, 15_000);

  it('mostra a visibilidade do material e permite publicar', async () => {
    const atualizar = vi
      .fn()
      .mockResolvedValue(material({ visibilidade: 'publicado' }));
    renderizar({ atualizarMaterial: atualizar });

    expect(await screen.findByText(M.materiais.rascunho)).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: /publicar/i }));

    expect(atualizar).toHaveBeenCalledWith(pacote.adaptacao_id, { visibilidade: 'publicado' });
  });

  it('edita o título do material e exibe o novo título', async () => {
    let materialAtual = material();
    const obterMaterial = vi.fn().mockImplementation(async () => ({
      material: materialAtual,
      pacote,
    }));
    const atualizarMaterial = vi.fn().mockImplementation(async (_id, dados) => {
      materialAtual = { ...materialAtual, ...dados };
      return materialAtual;
    });
    renderizar({ obterMaterial, atualizarMaterial });

    await screen.findByRole('heading', { name: 'Dominando Redes na Nuvem (catálogo)' });
    await userEvent.click(screen.getByRole('button', { name: /^editar$/i }));
    const dialogo = await screen.findByRole('dialog');
    const campo = within(dialogo).getByLabelText(/título do material/i);
    await userEvent.clear(campo);
    await userEvent.type(campo, 'Título editado');
    await userEvent.click(within(dialogo).getByRole('button', { name: /salvar/i }));

    expect(
      await screen.findByRole('heading', { name: 'Título editado' }),
    ).toBeInTheDocument();
    expect(atualizarMaterial).toHaveBeenCalledWith(pacote.adaptacao_id, {
      titulo: 'Título editado',
    });
  });

  it('trata 404 com mensagem específica e link para materiais', async () => {
    renderizar({
      obterMaterial: vi.fn().mockRejectedValue(
        new ErroApi(
          { erro: { codigo: 'MATERIAL_NAO_ENCONTRADO', mensagem: 'Material não encontrado.' } },
          404,
        ),
      ),
    });
    expect(await screen.findByRole('alert')).toHaveTextContent('Material não encontrado.');
    expect(screen.queryByRole('button', { name: M.comum.tentarNovamente })).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: /ir para materiais/i })).toHaveAttribute(
      'href',
      '/empresa/materiais',
    );
  });

  it('mostra "Tentar novamente" em erro genérico', async () => {
    renderizar({
      obterMaterial: vi
        .fn()
        .mockRejectedValue(new ErroApi({ erro: { codigo: 'INTERNO', mensagem: 'Falha no servidor.' } }, 500)),
    });
    expect(await screen.findByRole('alert')).toHaveTextContent('Falha no servidor.');
    expect(screen.getByRole('button', { name: M.comum.tentarNovamente })).toBeInTheDocument();
  });

  it('trata pacote fora do contrato sem tela branca', async () => {
    renderizar(
      {},
      {
        pacoteAtual: {
          ...pacote,
          metadados: { ...pacote.metadados, formato_gerado: 'Quiz' },
        } as unknown as AdaptacaoPacote,
      },
    );
    // String em vez de RegExp: `@vitest/browser` tipa o matcher só com string|number.
    expect(await screen.findByRole('alert')).toHaveTextContent('formato inesperado');
  });

  it('mostra erro quando o download JSON falha', async () => {
    const baixarJson = vi.fn().mockRejectedValue(
      new ErroApi({ erro: { codigo: 'INTERNO', mensagem: 'Falha ao baixar o pacote.' } }, 500),
    );
    renderizar({ baixarJson });
    await screen.findByRole('heading', { name: 'Dominando Redes na Nuvem (catálogo)' });

    await userEvent.click(screen.getByRole('button', { name: M.resultado.baixarJson }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Falha ao baixar o pacote.');
    expect(baixarJson).toHaveBeenCalledWith(pacote.adaptacao_id);
  });

  it('mantém o CSV focável, com aria-disabled e descrito pelo motivo', async () => {
    renderizar({}, { pacoteAtual: pacoteTutorial });
    await screen.findByRole('heading', { name: 'Dominando Redes na Nuvem (catálogo)' });

    const item = await abrirMenuCsv();

    expect(item).not.toHaveAttribute('disabled');
    expect(item).not.toHaveAttribute('data-disabled');
    expect(item).toHaveAttribute('aria-disabled', 'true');

    const id = item.getAttribute('aria-describedby');
    expect(id).toBeTruthy();
    expect(document.getElementById(id as string)).toHaveTextContent(M.resultado.csvIndisponivel);
  }, 15_000);

  it('abre o tooltip do CSV no foco do próprio item', async () => {
    renderizar({}, { pacoteAtual: pacoteTutorial });
    await screen.findByRole('heading', { name: 'Dominando Redes na Nuvem (catálogo)' });

    const item = await abrirMenuCsv();
    item.focus();

    expect(item).toHaveFocus();
    expect(await screen.findByRole('tooltip')).toHaveTextContent(M.resultado.csvIndisponivel);
  }, 15_000);

  it('abre o tooltip do CSV no hover do próprio item', async () => {
    renderizar({}, { pacoteAtual: pacoteTutorial });
    await screen.findByRole('heading', { name: 'Dominando Redes na Nuvem (catálogo)' });

    const item = await abrirMenuCsv();
    await userEvent.hover(item);

    expect(await screen.findByRole('tooltip')).toHaveTextContent(M.resultado.csvIndisponivel);
  }, 15_000);

  it('não exporta CSV em pacote não-Flashcards e mantém o item alcançável por teclado', async () => {
    const { api } = renderizar({}, { pacoteAtual: pacoteTutorial });
    await screen.findByRole('heading', { name: 'Dominando Redes na Nuvem (catálogo)' });

    const item = await abrirMenuCsv();
    item.focus();
    expect(item).toHaveFocus();

    await userEvent.keyboard('{Enter}');
    expect(vi.mocked(api.exportar)).not.toHaveBeenCalled();
  }, 15_000);

  it('exporta CSV quando o formato é Flashcards', async () => {
    URL.createObjectURL = vi.fn(() => 'blob:mock');
    URL.revokeObjectURL = vi.fn();
    const clique = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
    const { api } = renderizar();
    await screen.findByRole('heading', { name: 'Dominando Redes na Nuvem (catálogo)' });

    const item = await abrirMenuCsv();
    expect(item).not.toHaveAttribute('aria-disabled');

    await userEvent.click(item);

    await waitFor(() => expect(vi.mocked(api.exportar)).toHaveBeenCalledWith(pacote.adaptacao_id, 'csv'));
    expect(clique).toHaveBeenCalled();
  }, 15_000);
});
