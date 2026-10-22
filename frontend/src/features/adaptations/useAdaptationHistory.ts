'use client';

import { useQuery } from '@tanstack/react-query';
import { useRouter, useSearchParams } from 'next/navigation';
import { useCallback, useEffect, useMemo, useRef } from 'react';
import { useApi } from '@/services/api/ApiProvider';
import { ErroContrato } from '@/services/api/erros';
import { LIMITES, PaginaAdaptacoesSchema } from '@/types/schemas';

export interface FiltrosHistorico {
  pagina: number;
  formato?: string;
  perfil?: string;
  q: string;
}

function lerPagina(valor: string | null): number {
  const numero = Number.parseInt(valor ?? '1', 10);
  return Number.isFinite(numero) && numero >= 1 ? numero : 1;
}

export function useAdaptationHistory() {
  const api = useApi();
  const router = useRouter();
  const params = useSearchParams();

  const filtros = useMemo<FiltrosHistorico>(
    () => ({
      pagina: lerPagina(params.get('pagina')),
      formato: params.get('formato') ?? undefined,
      perfil: params.get('perfil') ?? undefined,
      q: params.get('q') ?? '',
    }),
    [params],
  );

  const atualizar = useCallback(
    (mudanca: Partial<FiltrosHistorico>) => {
      const proximos: FiltrosHistorico = { ...filtros, ...mudanca };
      const busca = new URLSearchParams();
      if (proximos.pagina > 1) busca.set('pagina', String(proximos.pagina));
      if (proximos.formato) busca.set('formato', proximos.formato);
      if (proximos.perfil) busca.set('perfil', proximos.perfil);
      if (proximos.q.trim()) busca.set('q', proximos.q.trim());
      const query = busca.toString();
      router.replace(query ? `/historico?${query}` : '/historico');
    },
    [filtros, router],
  );

  // O timer de busca precisa enxergar os filtros mais recentes mesmo quando o
  // usuário troca um filtro durante a janela de debounce.
  const atualizarRef = useRef(atualizar);
  useEffect(() => {
    atualizarRef.current = atualizar;
  }, [atualizar]);

  const timerBusca = useRef<ReturnType<typeof setTimeout> | null>(null);

  const setBusca = useCallback((valor: string) => {
    if (timerBusca.current !== null) clearTimeout(timerBusca.current);
    timerBusca.current = setTimeout(() => {
      timerBusca.current = null;
      atualizarRef.current({ q: valor, pagina: 1 });
    }, 300);
  }, []);

  useEffect(
    () => () => {
      if (timerBusca.current !== null) clearTimeout(timerBusca.current);
    },
    [],
  );

  const consulta = useQuery({
    queryKey: ['adaptacoes', filtros],
    queryFn: async () => {
      const bruto = await api.listar({
        pagina: filtros.pagina,
        tamanho_pagina: LIMITES.paginaPadrao,
        formato: filtros.formato,
        perfil: filtros.perfil,
        q: filtros.q,
      });
      const analisado = PaginaAdaptacoesSchema.safeParse(bruto);
      if (!analisado.success) {
        throw new ErroContrato(analisado.error.issues.map((i) => i.message).join('; '));
      }
      return analisado.data;
    },
    staleTime: 30_000,
  });

  return {
    data: consulta.data,
    isLoading: consulta.isLoading,
    error: consulta.error,
    refetch: consulta.refetch,
    filtros,
    busca: filtros.q,
    setBusca,
    atualizar,
  };
}
