import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, renderHook, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useAtualizarMaterial, useExcluirMaterial, useMateriais, useMaterial } from './useMateriais';
import { ApiProvider } from '@/services/api/ApiProvider';
import { ErroContrato } from '@/services/api/erros';
import type { NovaMenteApi } from '@/services/api/NovaMenteApi';
import type { MaterialDetalhe, MaterialResumo, PaginaMateriais } from '@/types/novamente';

const mocks = vi.hoisted(() => ({
  replace: vi.fn(),
  params: new URLSearchParams(),
}));

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: mocks.replace, push: vi.fn() }),
  useSearchParams: () => mocks.params,
}));

const material = (over: Partial<MaterialResumo> = {}): MaterialResumo => ({
  material_id: 'M1',
  adaptacao_id: 'A1',
  titulo: 'Material 1',
  documento_titulo: 'Documento 1',
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

const pagina = (itens: MaterialResumo[] = [material()]): PaginaMateriais => ({
  itens,
  pagina: 1,
  tamanho_pagina: 12,
  total: itens.length,
  total_paginas: itens.length > 0 ? 1 : 0,
});

function montar(api: Partial<NovaMenteApi>, client = new QueryClient({ defaultOptions: { queries: { retry: false } } })) {
  const cliente = {
    listarMateriais: vi.fn().mockResolvedValue(pagina()),
    obterMaterial: vi.fn().mockResolvedValue({ material: material(), pacote: {} }),
    atualizarMaterial: vi.fn().mockResolvedValue(material({ visibilidade: 'publicado' })),
    excluirMaterial: vi.fn().mockResolvedValue({ material_id: 'M1', removido: true, oci_removido: true }),
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

describe('useMateriais', () => {
  it('lê e valida os filtros da URL', async () => {
    mocks.params = new URLSearchParams(
      'q=vcn&formato=Quiz&perfil=Gestor&visibilidade=publicado&ordenar=titulo:asc&pagina=2',
    );
    const listarMateriais = vi.fn().mockResolvedValue(pagina());
    const { wrapper } = montar({ listarMateriais });

    const { result } = renderHook(() => useMateriais(), { wrapper });

    await waitFor(() => expect(result.current.data).toBeDefined());
    expect(listarMateriais).toHaveBeenCalledWith({
      pagina: 2,
      tamanho_pagina: 12,
      q: 'vcn',
      formato: 'Quiz',
      perfil: 'Gestor',
      visibilidade: 'publicado',
      ordenar: 'titulo:asc',
    });
    expect(result.current.filtros).toMatchObject({
      pagina: 2,
      q: 'vcn',
      formato: 'Quiz',
      perfil: 'Gestor',
      visibilidade: 'publicado',
      ordenar: 'titulo:asc',
    });
  });

  it('ignora filtros inválidos e usa os padrões', async () => {
    mocks.params = new URLSearchParams(
      'formato=Inexistente&perfil=Inexistente&visibilidade=oculto&ordenar=aleatoria&pagina=abc',
    );
    const listarMateriais = vi.fn().mockResolvedValue(pagina());
    const { wrapper } = montar({ listarMateriais });

    renderHook(() => useMateriais(), { wrapper });

    await waitFor(() =>
      expect(listarMateriais).toHaveBeenCalledWith({
        pagina: 1,
        tamanho_pagina: 12,
        q: '',
        formato: undefined,
        perfil: undefined,
        visibilidade: undefined,
        ordenar: 'criado_em:desc',
      }),
    );
  });

  it('reflete os filtros na URL', async () => {
    const { wrapper } = montar({});
    const { result } = renderHook(() => useMateriais(), { wrapper });

    act(() => result.current.atualizar({ visibilidade: 'publicado', pagina: 1 }));

    expect(mocks.replace).toHaveBeenCalledWith('/empresa/materiais?visibilidade=publicado');
  });

  it('busca com debounce de 300 ms', async () => {
    const { wrapper } = montar({});
    const { result } = renderHook(() => useMateriais(), { wrapper });

    act(() => result.current.setBusca('vcn'));

    expect(mocks.replace).not.toHaveBeenCalled();
    await waitFor(() => expect(mocks.replace).toHaveBeenCalledWith('/empresa/materiais?q=vcn'), {
      timeout: 1_500,
    });
  });
});

describe('useAtualizarMaterial', () => {
  it('invalida as listas e o catálogo do aluno', async () => {
    const atualizarMaterial = vi.fn().mockResolvedValue(material({ visibilidade: 'publicado' }));
    const { client, wrapper } = montar({ atualizarMaterial });
    const invalidar = vi.spyOn(client, 'invalidateQueries');

    const { result } = renderHook(() => useAtualizarMaterial(), { wrapper });
    await act(async () => {
      await result.current.mutateAsync({ materialId: 'M1', dados: { visibilidade: 'publicado' } });
    });

    expect(atualizarMaterial).toHaveBeenCalledWith('M1', { visibilidade: 'publicado' });
    const chaves = invalidar.mock.calls.map(([arg]) => arg?.queryKey);
    expect(chaves).toEqual(
      expect.arrayContaining([
        ['materiais'],
        ['material', 'M1'],
        ['aluno-catalogo'],
        ['vinculos'],
      ]),
    );
  });

  it('faz atualização otimista e reverte em erro', async () => {
    const atualizarMaterial = vi.fn().mockRejectedValue(new Error('falhou'));
    const { client, wrapper } = montar({ atualizarMaterial });
    client.setQueryData(['materiais', {}], {
      itens: [material()],
      pagina: 1,
      tamanho_pagina: 12,
      total: 1,
      total_paginas: 1,
    });

    const { result } = renderHook(() => useAtualizarMaterial(), { wrapper });
    await act(async () => {
      await result.current
        .mutateAsync({ materialId: 'M1', dados: { visibilidade: 'publicado' } })
        .catch(() => undefined);
    });

    const paginaAtual = client.getQueryData<PaginaMateriais>(['materiais', {}]);
    expect(paginaAtual?.itens[0].visibilidade).toBe('rascunho');
  });
});

describe('useExcluirMaterial', () => {
  it('invalida as listas, o detalhe e os vínculos', async () => {
    const excluirMaterial = vi
      .fn()
      .mockResolvedValue({ material_id: 'M1', removido: true, oci_removido: true });
    const { client, wrapper } = montar({ excluirMaterial });
    const invalidar = vi.spyOn(client, 'invalidateQueries');

    const { result } = renderHook(() => useExcluirMaterial(), { wrapper });
    await act(async () => {
      await result.current.mutateAsync('M1');
    });

    expect(excluirMaterial).toHaveBeenCalledWith('M1');
    const chaves = invalidar.mock.calls.map(([arg]) => arg?.queryKey);
    expect(chaves).toEqual(
      expect.arrayContaining([
        ['materiais'],
        ['material', 'M1'],
        ['aluno-catalogo'],
        ['vinculos'],
      ]),
    );
  });
});

describe('useMaterial', () => {
  it('devolve material e pacote validados', async () => {
    const pacote = {
      adaptacao_id: 'A1',
      status: 'sucesso',
      criado_em: '2026-10-21T14:02:11Z',
      documento: { titulo: 'Documento 1', origem: 'texto' },
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
        titulo: 'Material',
        introducao_contextualizada: 'Intro',
        itens: [
          { frente: 'Pergunta?', verso: 'Resposta.' },
          { frente: 'Pergunta 2?', verso: 'Resposta 2.' },
          { frente: 'Pergunta 3?', verso: 'Resposta 3.' },
        ],
      },
      avaliacao_qualidade: { ancoragem_fonte_score: 0.98, clareza_pedagogica: 'Alta' },
      armazenamento_oci: { bucket: 'novamente', objeto_id: 'a.json', status_upload: 'concluido' },
    } satisfies MaterialDetalhe['pacote'];
    const detalhe: MaterialDetalhe = { material: material(), pacote };
    const obterMaterial = vi.fn().mockResolvedValue(detalhe);
    const { wrapper } = montar({ obterMaterial });

    const { result } = renderHook(() => useMaterial('M1'), { wrapper });

    await waitFor(() => expect(result.current.data).toEqual(detalhe));
    expect(obterMaterial).toHaveBeenCalledWith('M1');
  });

  it('lança ErroContrato quando o detalhe viola o schema', async () => {
    const obterMaterial = vi.fn().mockResolvedValue({ material: { material_id: 'M1' } });
    const { wrapper } = montar({ obterMaterial });

    const { result } = renderHook(() => useMaterial('M1'), { wrapper });

    await waitFor(() => expect(result.current.error).toBeInstanceOf(ErroContrato));
  });
});
