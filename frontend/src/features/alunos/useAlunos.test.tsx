import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, renderHook, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  useAluno,
  useAlunos,
  useAtualizarAluno,
  useCriarAluno,
  useExcluirAluno,
} from './useAlunos';
import { ApiProvider } from '@/services/api/ApiProvider';
import { ErroContrato } from '@/services/api/erros';
import type { NovaMenteApi } from '@/services/api/NovaMenteApi';
import type { AlunoResumo, PaginaAlunos } from '@/types/novamente';

const mocks = vi.hoisted(() => ({
  replace: vi.fn(),
  params: new URLSearchParams(),
}));

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: mocks.replace, push: vi.fn() }),
  useSearchParams: () => mocks.params,
}));

const aluno = (over: Partial<AlunoResumo> = {}): AlunoResumo => ({
  aluno_id: 'A1',
  nome: 'Ana Beatriz Silva',
  email: 'ana.silva@exemplo.com',
  status: 'ativo',
  total_materiais: 0,
  criado_em: '2026-10-01T09:00:00Z',
  atualizado_em: '2026-10-01T09:00:00Z',
  ...over,
});

const pagina = (itens: AlunoResumo[] = [aluno()]): PaginaAlunos => ({
  itens,
  pagina: 1,
  tamanho_pagina: 12,
  total: itens.length,
  total_paginas: itens.length > 0 ? 1 : 0,
});

function montar(
  api: Partial<NovaMenteApi>,
  client = new QueryClient({ defaultOptions: { queries: { retry: false } } }),
) {
  const cliente = {
    listarAlunos: vi.fn().mockResolvedValue(pagina()),
    obterAluno: vi.fn().mockResolvedValue(aluno()),
    criarAluno: vi.fn().mockResolvedValue(aluno({ aluno_id: 'A2' })),
    atualizarAluno: vi.fn().mockResolvedValue(aluno({ nome: 'Ana Editada' })),
    excluirAluno: vi.fn().mockResolvedValue(undefined),
    ...api,
  } as unknown as NovaMenteApi;
  const wrapper = ({ children }: { children: ReactNode }) => (
    <ApiProvider client={cliente}>
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    </ApiProvider>
  );
  return { api: cliente, client, wrapper };
}

beforeEach(() => {
  mocks.replace.mockReset();
  mocks.params = new URLSearchParams();
});

describe('useAlunos', () => {
  it('lê e valida os filtros da URL', async () => {
    mocks.params = new URLSearchParams('q=ana&status=inativo&ordenar=nome:desc&pagina=2');
    const listarAlunos = vi.fn().mockResolvedValue(pagina());
    const { wrapper } = montar({ listarAlunos });

    const { result } = renderHook(() => useAlunos(), { wrapper });

    await waitFor(() => expect(result.current.data).toBeDefined());
    expect(listarAlunos).toHaveBeenCalledWith({
      pagina: 2,
      tamanho_pagina: 12,
      q: 'ana',
      status: 'inativo',
      ordenar: 'nome:desc',
    });
    expect(result.current.filtros).toMatchObject({
      pagina: 2,
      q: 'ana',
      status: 'inativo',
      ordenar: 'nome:desc',
    });
  });

  it('ignora filtros inválidos e usa os padrões', async () => {
    mocks.params = new URLSearchParams('status=desconhecido&ordenar=aleatoria&pagina=abc');
    const listarAlunos = vi.fn().mockResolvedValue(pagina());
    const { wrapper } = montar({ listarAlunos });

    renderHook(() => useAlunos(), { wrapper });

    await waitFor(() =>
      expect(listarAlunos).toHaveBeenCalledWith({
        pagina: 1,
        tamanho_pagina: 12,
        q: '',
        status: undefined,
        ordenar: 'nome:asc',
      }),
    );
  });

  it('reflete os filtros na URL', async () => {
    const { wrapper } = montar({});
    const { result } = renderHook(() => useAlunos(), { wrapper });

    act(() => result.current.atualizar({ status: 'ativo', pagina: 1 }));

    expect(mocks.replace).toHaveBeenCalledWith('/empresa/alunos?status=ativo');
  });

  it('busca com debounce de 300 ms', async () => {
    const { wrapper } = montar({});
    const { result } = renderHook(() => useAlunos(), { wrapper });

    act(() => result.current.setBusca('ana'));

    expect(mocks.replace).not.toHaveBeenCalled();
    await waitFor(() => expect(mocks.replace).toHaveBeenCalledWith('/empresa/alunos?q=ana'), {
      timeout: 1_500,
    });
  });
});

describe('useAluno', () => {
  it('devolve o aluno validado', async () => {
    const obterAluno = vi.fn().mockResolvedValue(aluno());
    const { wrapper } = montar({ obterAluno });

    const { result } = renderHook(() => useAluno('A1'), { wrapper });

    await waitFor(() => expect(result.current.data).toEqual(aluno()));
    expect(obterAluno).toHaveBeenCalledWith('A1');
  });

  it('lança ErroContrato quando o aluno viola o schema', async () => {
    const obterAluno = vi.fn().mockResolvedValue({ aluno_id: 'A1' });
    const { wrapper } = montar({ obterAluno });

    const { result } = renderHook(() => useAluno('A1'), { wrapper });

    await waitFor(() => expect(result.current.error).toBeInstanceOf(ErroContrato));
  });
});

describe('mutações de aluno', () => {
  it('criar invalida a lista e registra o detalhe', async () => {
    const criarAluno = vi.fn().mockResolvedValue(aluno({ aluno_id: 'A2' }));
    const { client, wrapper } = montar({ criarAluno });
    const invalidar = vi.spyOn(client, 'invalidateQueries');

    const { result } = renderHook(() => useCriarAluno(), { wrapper });
    await act(async () => {
      await result.current.mutateAsync({
        nome: 'Ana',
        email: 'ana@exemplo.com',
        status: 'ativo',
      });
    });

    expect(criarAluno).toHaveBeenCalledWith({
      nome: 'Ana',
      email: 'ana@exemplo.com',
      status: 'ativo',
    });
    const chaves = invalidar.mock.calls.map(([arg]) => arg?.queryKey);
    expect(chaves).toEqual(
      expect.arrayContaining([['alunos'], ['aluno', 'A2'], ['vinculos', 'A2']]),
    );
    expect(client.getQueryData(['aluno', 'A2'])).toEqual(aluno({ aluno_id: 'A2' }));
  });

  it('atualizar invalida lista, detalhe e vínculos', async () => {
    const { client, wrapper } = montar({});
    const invalidar = vi.spyOn(client, 'invalidateQueries');

    const { result } = renderHook(() => useAtualizarAluno(), { wrapper });
    await act(async () => {
      await result.current.mutateAsync({ alunoId: 'A1', dados: { nome: 'Ana Editada' } });
    });

    const chaves = invalidar.mock.calls.map(([arg]) => arg?.queryKey);
    expect(chaves).toEqual(
      expect.arrayContaining([['alunos'], ['aluno', 'A1'], ['vinculos', 'A1']]),
    );
  });

  it('excluir invalida lista, detalhe e vínculos', async () => {
    const excluirAluno = vi.fn().mockResolvedValue(undefined);
    const { client, wrapper } = montar({ excluirAluno });
    const invalidar = vi.spyOn(client, 'invalidateQueries');

    const { result } = renderHook(() => useExcluirAluno(), { wrapper });
    await act(async () => {
      await result.current.mutateAsync('A1');
    });

    expect(excluirAluno).toHaveBeenCalledWith('A1');
    const chaves = invalidar.mock.calls.map(([arg]) => arg?.queryKey);
    expect(chaves).toEqual(
      expect.arrayContaining([['alunos'], ['aluno', 'A1'], ['vinculos', 'A1']]),
    );
  });
});
