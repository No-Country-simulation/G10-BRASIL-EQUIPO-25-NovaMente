import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, renderHook } from '@testing-library/react';
import type { ReactNode } from 'react';
import { describe, expect, it, vi } from 'vitest';
import { ErroAplicarVinculos, useAplicarVinculos } from './useVinculos';
import { ApiProvider } from '@/services/api/ApiProvider';
import type { NovaMenteApi } from '@/services/api/NovaMenteApi';
import type { VinculoMaterial } from '@/types/novamente';

const vinculo = (materialId: string): VinculoMaterial => ({
  material_id: materialId,
  titulo: `Material ${materialId}`,
  formato: 'Flashcards',
  perfil: 'Iniciante',
  visibilidade: 'publicado',
  vinculado_em: '2026-10-01T09:00:00Z',
});

function montar(api: Partial<NovaMenteApi>) {
  const cliente = {
    adicionarVinculo: vi.fn(),
    removerVinculo: vi.fn(),
    ...api,
  } as unknown as NovaMenteApi;
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const wrapper = ({ children }: { children: ReactNode }) => (
    <ApiProvider client={cliente}>
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    </ApiProvider>
  );
  return { api: cliente, client, wrapper };
}

const chavesInvalidadas = (invalidar: { mock: { calls: unknown[][] } }) =>
  invalidar.mock.calls.map(([arg]) => (arg as { queryKey?: unknown })?.queryKey);

describe('useAplicarVinculos', () => {
  it('mapeia a diferença para adicionar/remover e invalida as consultas', async () => {
    const adicionarVinculo = vi.fn().mockResolvedValue(vinculo('M2'));
    const removerVinculo = vi.fn().mockResolvedValue(undefined);
    const { client, wrapper } = montar({ adicionarVinculo, removerVinculo });
    const invalidar = vi.spyOn(client, 'invalidateQueries');

    const { result } = renderHook(() => useAplicarVinculos('A1'), { wrapper });
    await act(async () => {
      await result.current.mutateAsync({ adicionar: ['M2'], remover: ['M1'] });
    });

    expect(adicionarVinculo).toHaveBeenCalledWith('A1', 'M2');
    expect(removerVinculo).toHaveBeenCalledWith('A1', 'M1');
    expect(chavesInvalidadas(invalidar)).toEqual(
      expect.arrayContaining([['vinculos', 'A1'], ['materiais'], ['aluno', 'A1']]),
    );
  });

  it('mantém as demais operações, relata a falha e ainda invalida as consultas', async () => {
    const adicionarVinculo = vi.fn((_alunoId: string, materialId: string) =>
      materialId === 'M2'
        ? Promise.reject(new Error('falhou'))
        : Promise.resolve(vinculo(materialId)),
    );
    const removerVinculo = vi.fn().mockResolvedValue(undefined);
    const { client, wrapper } = montar({ adicionarVinculo, removerVinculo });
    const invalidar = vi.spyOn(client, 'invalidateQueries');

    const { result } = renderHook(() => useAplicarVinculos('A1'), { wrapper });

    let erro: unknown;
    await act(async () => {
      try {
        await result.current.mutateAsync({ adicionar: ['M2', 'M3'], remover: ['M1'] });
      } catch (e) {
        erro = e;
      }
    });

    expect(erro).toBeInstanceOf(ErroAplicarVinculos);
    expect((erro as ErroAplicarVinculos).falhas).toEqual([
      { materialId: 'M2', operacao: 'adicionar' },
    ]);
    expect(adicionarVinculo).toHaveBeenCalledWith('A1', 'M3');
    expect(removerVinculo).toHaveBeenCalledWith('A1', 'M1');
    expect(chavesInvalidadas(invalidar)).toEqual(
      expect.arrayContaining([['vinculos', 'A1'], ['materiais'], ['aluno', 'A1']]),
    );
  });
});
