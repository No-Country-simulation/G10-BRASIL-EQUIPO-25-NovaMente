'use client';

import { useQuery } from '@tanstack/react-query';
import { useApi } from '@/services/api/ApiProvider';
import { ErroContrato } from '@/services/api/erros';
import { AdaptacaoPacoteSchema } from '@/types/schemas';

export function useAdaptation(adaptacaoId: string) {
  const api = useApi();

  return useQuery({
    queryKey: ['adaptacao', adaptacaoId],
    queryFn: async () => {
      const bruto = await api.obter(adaptacaoId);
      const analisado = AdaptacaoPacoteSchema.safeParse(bruto);
      if (!analisado.success) {
        throw new ErroContrato(analisado.error.issues.map((i) => i.message).join('; '));
      }
      return analisado.data;
    },
    staleTime: Infinity,
    retry: false,
  });
}
