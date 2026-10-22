import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { ResultadoView } from './ResultadoView';
import { M } from '@/lib/mensagens';
import { ApiProvider } from '@/services/api/ApiProvider';
import { ErroApi } from '@/services/api/erros';
import type { NovaMenteApi } from '@/services/api/NovaMenteApi';
import type { AdaptacaoPacote } from '@/types/novamente';

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

function renderizar(sobrescrever: Partial<NovaMenteApi> = {}) {
  const api = {
    obter: vi.fn().mockResolvedValue(pacote),
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
        <ResultadoView adaptacaoId={pacote.adaptacao_id} />
      </QueryClientProvider>
    </ApiProvider>,
  );
  return { api };
}

async function abrirMenuExportar() {
  await userEvent.click(screen.getByRole('button', { name: M.resultado.exportar }));
  const item = await screen.findByRole('menuitem', { name: 'CSV (Anki)' });
  const wrapper = item.parentElement;
  expect(wrapper?.tagName).toBe('SPAN');
  expect(wrapper).toHaveAttribute('tabindex', '0');
  return { item, wrapper: wrapper as HTMLElement };
}

describe('ResultadoView', () => {
  it('renderiza título, deck e painel OCI', async () => {
    renderizar();
    expect(await screen.findByRole('heading', { name: 'Dominando Redes na Nuvem' })).toBeInTheDocument();
    expect(await screen.findByText('O que é VCN?')).toBeInTheDocument();
    expect(screen.getByText('98%')).toBeInTheDocument();
  });

  it('trata 404 com mensagem específica e sem "Tentar novamente"', async () => {
    renderizar({
      obter: vi.fn().mockRejectedValue(
        new ErroApi({ erro: { codigo: 'ADAPTACAO_NAO_ENCONTRADA', mensagem: 'Material não encontrado.' } }, 404),
      ),
    });
    expect(await screen.findByRole('alert')).toHaveTextContent('Material não encontrado.');
    expect(screen.queryByRole('button', { name: M.comum.tentarNovamente })).not.toBeInTheDocument();
  });

  it('mostra "Tentar novamente" em erro genérico', async () => {
    renderizar({
      obter: vi
        .fn()
        .mockRejectedValue(new ErroApi({ erro: { codigo: 'INTERNO', mensagem: 'Falha no servidor.' } }, 500)),
    });
    expect(await screen.findByRole('alert')).toHaveTextContent('Falha no servidor.');
    expect(screen.getByRole('button', { name: M.comum.tentarNovamente })).toBeInTheDocument();
  });

  it('trata pacote fora do contrato sem tela branca', async () => {
    renderizar({
      obter: vi.fn().mockResolvedValue({
        ...pacote,
        metadados: { ...pacote.metadados, formato_gerado: 'Quiz' },
      }),
    });
    // String em vez de RegExp: `@vitest/browser` tipa o matcher só com string|number.
    expect(await screen.findByRole('alert')).toHaveTextContent('formato inesperado');
  });

  it('mostra erro quando o download JSON falha', async () => {
    const baixarJson = vi.fn().mockRejectedValue(
      new ErroApi({ erro: { codigo: 'INTERNO', mensagem: 'Falha ao baixar o pacote.' } }, 500),
    );
    renderizar({ baixarJson });
    await screen.findByRole('heading', { name: 'Dominando Redes na Nuvem' });

    await userEvent.click(screen.getByRole('button', { name: M.resultado.baixarJson }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Falha ao baixar o pacote.');
    expect(baixarJson).toHaveBeenCalledWith(pacote.adaptacao_id);
  });

  it('desabilita CSV para Tutorial e mostra o motivo no foco do wrapper', async () => {
    renderizar({ obter: vi.fn().mockResolvedValue(pacoteTutorial) });
    await screen.findByRole('heading', { name: pacoteTutorial.conteudo_adaptado.titulo });

    const { item, wrapper } = await abrirMenuExportar();

    expect(item).toHaveAttribute('data-disabled');
    wrapper.focus();
    expect(await screen.findByText(M.resultado.csvIndisponivel)).toBeInTheDocument();
  });

  it('mostra o motivo do CSV desabilitado no hover do wrapper', async () => {
    renderizar({ obter: vi.fn().mockResolvedValue(pacoteTutorial) });
    await screen.findByRole('heading', { name: pacoteTutorial.conteudo_adaptado.titulo });

    const { wrapper } = await abrirMenuExportar();

    await userEvent.hover(wrapper);
    expect(await screen.findByText(M.resultado.csvIndisponivel)).toBeInTheDocument();
  });
});
