import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { ResultadoView } from './ResultadoView';
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

function renderizar(obter: NovaMenteApi['obter']) {
  const api = {
    obter,
    statusOci: vi.fn().mockResolvedValue({
      configurado: true,
      bucket: 'novamente',
      verificado_em: '2026-10-21T14:00:00Z',
    }),
    exportar: vi.fn().mockResolvedValue(new Blob(['x'])),
    baixarJson: vi.fn().mockResolvedValue(new Blob(['{}'])),
  } as unknown as NovaMenteApi;
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <ApiProvider client={api}>
      <QueryClientProvider client={client}>
        <ResultadoView adaptacaoId={pacote.adaptacao_id} />
      </QueryClientProvider>
    </ApiProvider>,
  );
}

describe('ResultadoView', () => {
  it('renderiza título, deck e painel OCI', async () => {
    renderizar(vi.fn().mockResolvedValue(pacote));
    expect(await screen.findByRole('heading', { name: 'Dominando Redes na Nuvem' })).toBeInTheDocument();
    expect(await screen.findByText('O que é VCN?')).toBeInTheDocument();
    expect(screen.getByText('98%')).toBeInTheDocument();
  });

  it('trata 404 com mensagem específica', async () => {
    renderizar(
      vi.fn().mockRejectedValue(
        new ErroApi({ erro: { codigo: 'ADAPTACAO_NAO_ENCONTRADA', mensagem: 'Material não encontrado.' } }, 404),
      ),
    );
    expect(await screen.findByRole('alert')).toHaveTextContent('Material não encontrado.');
  });

  it('trata pacote fora do contrato sem tela branca', async () => {
    renderizar(
      vi.fn().mockResolvedValue({
        ...pacote,
        metadados: { ...pacote.metadados, formato_gerado: 'Quiz' },
      }),
    );
    // String em vez de RegExp: `@vitest/browser` tipa o matcher só com string|number.
    expect(await screen.findByRole('alert')).toHaveTextContent('formato inesperado');
  });
});
