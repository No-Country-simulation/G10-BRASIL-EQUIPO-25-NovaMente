import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { AlunoDetalheView } from './AlunoDetalheView';
import { ApiProvider } from '@/services/api/ApiProvider';
import { ErroApi } from '@/services/api/erros';
import type { NovaMenteApi } from '@/services/api/NovaMenteApi';
import type {
  AlunoResumo,
  MaterialResumo,
  PaginaMateriais,
  VinculoMaterial,
} from '@/types/novamente';

const mocks = vi.hoisted(() => ({
  replace: vi.fn(),
  push: vi.fn(),
  params: new URLSearchParams(),
}));

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: mocks.replace, push: mocks.push }),
  useSearchParams: () => mocks.params,
}));

const aluno = (over: Partial<AlunoResumo> = {}): AlunoResumo => ({
  aluno_id: 'A1',
  nome: 'Ana Beatriz Silva',
  email: 'ana.silva@exemplo.com',
  status: 'ativo',
  total_materiais: 2,
  criado_em: '2026-10-01T09:00:00Z',
  atualizado_em: '2026-10-01T09:00:00Z',
  ...over,
});

const material = (over: Partial<MaterialResumo> = {}): MaterialResumo => {
  const base: MaterialResumo = {
    material_id: 'M1',
    adaptacao_id: 'M1',
    titulo: 'Material M1',
    documento_titulo: 'Documento M1',
    perfil: 'Iniciante',
    formato: 'Flashcards',
    nivel: 'Didatico',
    nicho: 'Geral',
    visibilidade: 'publicado',
    tempo_estimado_estudo_minutos: 10,
    ancoragem_fonte_score: 0.9,
    status_upload: 'concluido',
    criado_em: '2026-10-01T09:00:00Z',
    atualizado_em: '2026-10-01T09:00:00Z',
    ...over,
  };
  return {
    ...base,
    titulo: over.titulo ?? `Material ${base.material_id}`,
    documento_titulo: over.documento_titulo ?? `Documento ${base.material_id}`,
  };
};

const pagina = (itens: MaterialResumo[] = [material()]): PaginaMateriais => ({
  itens,
  pagina: 1,
  tamanho_pagina: 12,
  total: itens.length,
  total_paginas: itens.length > 0 ? 1 : 0,
});

const vinculo = (materialId: string): VinculoMaterial => ({
  material_id: materialId,
  titulo: `Material ${materialId}`,
  formato: 'Flashcards',
  perfil: 'Iniciante',
  visibilidade: 'publicado',
  vinculado_em: '2026-10-01T09:00:00Z',
});

function renderComApi(ui: ReactNode, api: Partial<NovaMenteApi> = {}) {
  const cliente = {
    obterAluno: vi.fn().mockResolvedValue(aluno()),
    atualizarAluno: vi.fn().mockResolvedValue(aluno({ nome: 'Ana Editada' })),
    excluirAluno: vi.fn().mockResolvedValue(undefined),
    listarMateriais: vi.fn().mockResolvedValue(pagina()),
    listarVinculos: vi.fn().mockResolvedValue({ aluno_id: 'A1', itens: [vinculo('M1')] }),
    ...api,
  } as unknown as NovaMenteApi;
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <ApiProvider client={cliente}>
      <QueryClientProvider client={client}>{ui}</QueryClientProvider>
    </ApiProvider>,
  );
  return { api: cliente, client };
}

beforeEach(() => {
  mocks.replace.mockReset();
  mocks.push.mockReset();
  mocks.params = new URLSearchParams();
});

describe('AlunoDetalheView', () => {
  it('mostra os dados do aluno, os vínculos e o link de volta com a query', async () => {
    mocks.params = new URLSearchParams('pagina=2&status=ativo');
    renderComApi(<AlunoDetalheView alunoId="A1" />);

    expect(await screen.findByRole('heading', { name: 'Ana Beatriz Silva' })).toBeInTheDocument();
    expect(screen.getByText('ana.silva@exemplo.com')).toBeInTheDocument();
    expect(screen.getByText('2 materiais')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /materiais vinculados/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /voltar para alunos/i })).toHaveAttribute(
      'href',
      '/empresa/alunos?pagina=2&status=ativo',
    );
  });

  it('edita o aluno pelo diálogo', async () => {
    const atualizar = vi.fn().mockResolvedValue(aluno({ nome: 'Ana Editada' }));
    renderComApi(<AlunoDetalheView alunoId="A1" />, { atualizarAluno: atualizar });

    await userEvent.click(await screen.findByRole('button', { name: /^editar$/i }));
    const dialogo = await screen.findByRole('dialog');
    const campo = within(dialogo).getByLabelText(/nome/i);
    await userEvent.clear(campo);
    await userEvent.type(campo, 'Ana Editada');
    await userEvent.click(within(dialogo).getByRole('button', { name: /salvar/i }));

    await waitFor(() =>
      expect(atualizar).toHaveBeenCalledWith('A1', {
        nome: 'Ana Editada',
        email: 'ana.silva@exemplo.com',
        status: 'ativo',
      }),
    );
    expect(await screen.findByRole('status')).toHaveTextContent('Aluno atualizado.');
  });

  it('exclui o aluno e volta para a lista', async () => {
    mocks.params = new URLSearchParams('pagina=3');
    const excluir = vi.fn().mockResolvedValue(undefined);
    renderComApi(<AlunoDetalheView alunoId="A1" />, { excluirAluno: excluir });

    await userEvent.click(await screen.findByRole('button', { name: /^excluir$/i }));
    const dialogo = await screen.findByRole('dialog');
    await userEvent.click(within(dialogo).getByRole('button', { name: /confirmar e excluir/i }));

    await waitFor(() => expect(excluir).toHaveBeenCalledWith('A1'));
    await waitFor(() => expect(mocks.push).toHaveBeenCalledWith('/empresa/alunos?pagina=3'));
  });

  it('mostra aluno não encontrado', async () => {
    renderComApi(<AlunoDetalheView alunoId="A1" />, {
      obterAluno: vi.fn().mockRejectedValue(
        new ErroApi(
          {
            erro: {
              codigo: 'ALUNO_NAO_ENCONTRADO',
              mensagem: 'Aluno não encontrado.',
            },
          },
          404,
        ),
      ),
    });

    expect(await screen.findByRole('alert')).toHaveTextContent('Aluno não encontrado.');
    expect(screen.getByRole('link', { name: /voltar para alunos/i })).toBeInTheDocument();
  });
});
