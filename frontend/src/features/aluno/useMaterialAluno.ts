'use client';

import { useQuery } from '@tanstack/react-query';
import { useApi } from '@/services/api/ApiProvider';
import { ErroContrato } from '@/services/api/erros';
import { MaterialDetalheSchema } from '@/types/schemas';
import { useIdentidadeAluno } from './useIdentidadeAluno';

/**
 * Detalhe de um material na área do aluno. O `aluno_id` vem da identidade
 * persistida: o servidor só devolve material publicado e vinculado a ele.
 */
export function useMaterialAluno(materialId: string) {
  const api = useApi();
  const { aluno } = useIdentidadeAluno();
  const alunoId = aluno?.aluno_id ?? '';

  return useQuery({
    queryKey: ['aluno-material', alunoId, materialId],
    queryFn: async () => {
      const bruto = await api.obterMaterialAluno(alunoId, materialId);
      const analisado = MaterialDetalheSchema.safeParse(bruto);
      if (!analisado.success) {
        throw new ErroContrato(analisado.error.issues.map((i) => i.message).join('; '));
      }
      return analisado.data;
    },
    enabled: Boolean(alunoId && materialId),
    staleTime: 30_000,
    retry: false,
  });
}
