import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { AlunoMaterialView } from './AlunoMaterialView';
import { CHAVE_IDENTIDADE_ALUNO } from '@/features/aluno/useIdentidadeAluno';
import { M } from '@/lib/mensagens';
import { ApiProvider } from '@/services/api/ApiProvider';
import { ErroApi } from '@/services/api/erros';
import type { NovaMenteApi } from '@/services/api/NovaMenteApi';
import type { AdaptacaoPacote, MaterialResumo } from '@/types/novamente';

const mocks = vi.hoisted(() => ({
  replace: vi.fn(),
  push: vi.fn(),
}));

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: mocks.replace, push: mocks.push }),
}));

const pacote: AdaptacaoPacote = {
  adaptacao_id: 'M1',
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
    introducao_contextualizada: 'Intro do material.',
    itens: [
      { frente: 'O que é VCN?', verso: 'Rede privada.' },
      { frente: 'O que é subnet?', verso: 'Divisão da rede.' },
      { frente: 'O que é IGW?', verso: 'Porta para a internet.' },
    ],
  },
  avaliacao_qualidade: { ancoragem_fonte_score: 0.98, clareza_pedagogica: 'Alta' },
  armazenamento_oci: { bucket: 'novamente', objeto_id: 'a.json', status_upload: 'concluido' },
};

const material: MaterialResumo = {
  material_id: 'M1',
  adaptacao_id: 'M1',
  titulo: 'Dominando Redes na Nuvem',
  documento_titulo: 'Introdução à VCN',
  perfil: 'Iniciante',
  formato: 'Flashcards',
  nivel: 'Didatico',
  nicho: 'Geral',
  visibilidade: 'publicado',
  tempo_estimado_estudo_minutos: 5,
  ancoragem_fonte_score: 0.98,
  status_upload: 'concluido',
  criado_em: '2026-10-21T14:02:11Z',
  atualizado_em: '2026-10-21T14:02:11Z',
};

function renderMaterial(api: Partial<NovaMenteApi> = {}) {
  const cliente = {
    obterMaterialAluno: vi.fn().mockResolvedValue({ material, pacote }),
    ...api,
  } as unknown as NovaMenteApi;
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <ApiProvider client={cliente}>
      <QueryClientProvider client={client}>
        <AlunoMaterialView materialId="M1" />
      </QueryClientProvider>
    </ApiProvider>,
  );
  return { api: cliente };
}

function identificar() {
  window.localStorage.setItem(
    CHAVE_IDENTIDADE_ALUNO,
    JSON.stringify({ aluno_id: 'A1', nome: 'Ana Beatriz' }),
  );
}

beforeEach(() => {
  mocks.replace.mockReset();
  mocks.push.mockReset();
  window.localStorage.clear();
});

describe('AlunoMaterialView', () => {
  it('renderiza o material sem OCI e sem exportação', async () => {
    identificar();
    const { api } = renderMaterial();

    expect(
      await screen.findByRole('heading', { name: 'Dominando Redes na Nuvem' }),
    ).toBeInTheDocument();
    expect(await screen.findByText('O que é VCN?')).toBeInTheDocument();
    expect(screen.getByText('Intro do material.')).toBeInTheDocument();
    expect(vi.mocked(api.obterMaterialAluno)).toHaveBeenCalledWith('A1', 'M1');

    expect(screen.queryByText(M.oci.titulo)).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: M.resultado.exportar })).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: M.aluno.material.voltarCatalogo })).toHaveAttribute(
      'href',
      '/aluno',
    );
  }, 15_000);

  it('mostra indisponível quando o material não está liberado', async () => {
    identificar();
    renderMaterial({
      obterMaterialAluno: vi.fn().mockRejectedValue(
        new ErroApi(
          {
            erro: {
              codigo: 'MATERIAL_NAO_DISPONIVEL',
              mensagem: 'Material não disponível.',
            },
          },
          404,
        ),
      ),
    });

    expect(await screen.findByText(M.aluno.material.indisponivel)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: M.aluno.material.voltarCatalogo })).toHaveAttribute(
      'href',
      '/aluno',
    );
  });

  it('limpa a identidade quando o aluno não existe mais no servidor', async () => {
    identificar();
    renderMaterial({
      obterMaterialAluno: vi.fn().mockRejectedValue(
        new ErroApi(
          { erro: { codigo: 'ALUNO_NAO_ENCONTRADO', mensagem: 'Aluno não encontrado.' } },
          404,
        ),
      ),
    });

    await waitFor(() => expect(mocks.replace).toHaveBeenCalledWith('/aluno'));
    expect(window.localStorage.getItem(CHAVE_IDENTIDADE_ALUNO)).toBeNull();
    expect(await screen.findByText(M.aluno.material.identifiqueSe)).toBeInTheDocument();
  });

  it('limpa a identidade e volta ao catálogo quando o aluno está inativo', async () => {
    identificar();
    renderMaterial({
      obterMaterialAluno: vi.fn().mockRejectedValue(
        new ErroApi(
          { erro: { codigo: 'ALUNO_INATIVO', mensagem: 'Aluno inativo.' } },
          403,
        ),
      ),
    });

    await waitFor(() => expect(mocks.replace).toHaveBeenCalledWith('/aluno'));
    expect(window.localStorage.getItem(CHAVE_IDENTIDADE_ALUNO)).toBeNull();
    expect(await screen.findByText(M.aluno.material.identifiqueSe)).toBeInTheDocument();
  });

  it('pede identificação quando não há aluno na sessão', async () => {
    const { api } = renderMaterial();

    expect(screen.getByText(M.aluno.material.identifiqueSe)).toBeInTheDocument();
    expect(
      screen.getByRole('link', { name: M.aluno.material.irParaIdentificacao }),
    ).toHaveAttribute('href', '/aluno');
    expect(vi.mocked(api.obterMaterialAluno)).not.toHaveBeenCalled();
  });
});
