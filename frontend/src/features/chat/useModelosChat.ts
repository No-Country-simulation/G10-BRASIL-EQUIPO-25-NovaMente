'use client';

import { useQuery } from '@tanstack/react-query';
import { useApi } from '@/services/api/ApiProvider';
import { ErroContrato } from '@/services/api/erros';
import { ModelosChatSchema } from '@/types/schemas';

/** Modelos que o backend aceita no chat e o padrão. Falha aqui só esconde o seletor. */
export function useModelosChat() {
  const api = useApi();

  return useQuery({
    queryKey: ['chat-modelos'],
    queryFn: async () => {
      const bruto = await api.listarModelosChat();
      const analisado = ModelosChatSchema.safeParse(bruto);
      if (!analisado.success) {
        throw new ErroContrato(analisado.error.issues.map((i) => i.message).join('; '));
      }
      return analisado.data;
    },
    staleTime: 5 * 60_000,
    retry: false,
  });
}
