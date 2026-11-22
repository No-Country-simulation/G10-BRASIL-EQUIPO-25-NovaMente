'use client';

import { useQuery } from '@tanstack/react-query';
import { useApi } from '@/services/api/ApiProvider';
import { ErroContrato } from '@/services/api/erros';
import { MaterialDetalheSchema } from '@/types/schemas';

export function useMaterial(materialId: string) {
  const api = useApi();

  return useQuery({
    queryKey: ['material', materialId],
    queryFn: async () => {
      const bruto = await api.obterMaterial(materialId);
      const analisado = MaterialDetalheSchema.safeParse(bruto);
      if (!analisado.success) {
        throw new ErroContrato(analisado.error.issues.map((i) => i.message).join('; '));
      }
      return analisado.data;
    },
    staleTime: 30_000,
    retry: false,
  });
}
