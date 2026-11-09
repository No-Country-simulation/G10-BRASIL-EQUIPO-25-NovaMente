'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useApi } from '@/services/api/ApiProvider';
import { ErroContrato } from '@/services/api/erros';
import { VinculosAlunoSchema } from '@/types/schemas';

export interface DiferencaVinculos {
  adicionar: string[];
  remover: string[];
}

export interface FalhaVinculo {
  materialId: string;
  operacao: 'adicionar' | 'remover';
}

/** Algumas operações da diferença falharam; as demais foram aplicadas. */
export class ErroAplicarVinculos extends Error {
  constructor(public readonly falhas: FalhaVinculo[]) {
    super('Não foi possível aplicar todos os vínculos.');
    this.name = 'ErroAplicarVinculos';
  }
}

export function useVinculos(alunoId: string) {
  const api = useApi();

  return useQuery({
    queryKey: ['vinculos', alunoId],
    queryFn: async () => {
      const bruto = await api.listarVinculos(alunoId);
      const analisado = VinculosAlunoSchema.safeParse(bruto);
      if (!analisado.success) {
        throw new ErroContrato(analisado.error.issues.map((i) => i.message).join('; '));
      }
      return analisado.data;
    },
    enabled: Boolean(alunoId),
    staleTime: 30_000,
    retry: false,
  });
}

/**
 * Aplica apenas a diferença escolhida pelo usuário. A lista de materiais é
 * paginada e filtrada, então enviar o conjunto inteiro desvincularia o que
 * está fora da página visível.
 */
export function useAplicarVinculos(alunoId: string) {
  const api = useApi();
  const queryClient = useQueryClient();

  return useMutation<void, unknown, DiferencaVinculos>({
    mutationFn: async ({ adicionar, remover }) => {
      const operacoes = [
        ...adicionar.map((materialId) => ({
          materialId,
          operacao: 'adicionar' as const,
          executar: () => api.adicionarVinculo(alunoId, materialId),
        })),
        ...remover.map((materialId) => ({
          materialId,
          operacao: 'remover' as const,
          executar: () => api.removerVinculo(alunoId, materialId),
        })),
      ];

      const resultados = await Promise.allSettled(operacoes.map((o) => o.executar()));
      const falhas = resultados.flatMap((resultado, indice) =>
        resultado.status === 'rejected'
          ? [{ materialId: operacoes[indice].materialId, operacao: operacoes[indice].operacao }]
          : [],
      );

      if (falhas.length > 0) throw new ErroAplicarVinculos(falhas);
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ['vinculos', alunoId] });
      queryClient.invalidateQueries({ queryKey: ['materiais'] });
      queryClient.invalidateQueries({ queryKey: ['aluno', alunoId] });
      queryClient.invalidateQueries({ queryKey: ['alunos'] });
    },
  });
}
