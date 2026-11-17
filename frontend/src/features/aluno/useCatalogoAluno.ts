'use client';

import { useQuery } from '@tanstack/react-query';
import { useRouter, useSearchParams } from 'next/navigation';
import { useCallback, useEffect, useMemo, useRef } from 'react';
import { useApi } from '@/services/api/ApiProvider';
import { ErroContrato } from '@/services/api/erros';
import { formatoSaidaSchema, LIMITES, PaginaCatalogoAlunoSchema } from '@/types/schemas';
import type { FormatoSaida } from '@/types/novamente';
import { ROTAS } from '@/lib/rotas';

export interface FiltrosCatalogoAluno {
  pagina: number;
  q: string;
  formato?: FormatoSaida;
}

function lerPagina(valor: string | null): number {
  const numero = Number.parseInt(valor ?? '1', 10);
  return Number.isFinite(numero) && numero >= 1 ? numero : 1;
}

function lerFormato(valor: string | null): FormatoSaida | undefined {
  if (!valor) return undefined;
  const analisado = formatoSaidaSchema.safeParse(valor);
  return analisado.success ? analisado.data : undefined;
}

export function useCatalogoAluno(alunoId: string) {
  const api = useApi();
  const router = useRouter();
  const params = useSearchParams();

  const filtros = useMemo<FiltrosCatalogoAluno>(
    () => ({
      pagina: lerPagina(params.get('pagina')),
      q: params.get('q') ?? '',
      formato: lerFormato(params.get('formato')),
    }),
    [params],
  );

  const atualizar = useCallback(
    (mudanca: Partial<FiltrosCatalogoAluno>) => {
      const proximos: FiltrosCatalogoAluno = { ...filtros, ...mudanca };
      const busca = new URLSearchParams();
      if (proximos.pagina > 1) busca.set('pagina', String(proximos.pagina));
      if (proximos.formato) busca.set('formato', proximos.formato);
      if (proximos.q.trim()) busca.set('q', proximos.q.trim());
      const query = busca.toString();
      router.replace(query ? `${ROTAS.aluno}?${query}` : ROTAS.aluno);
    },
    [filtros, router],
  );

  // O timer precisa enxergar os filtros mais recentes mesmo quando outro
  // filtro muda durante a janela de debounce.
  const atualizarRef = useRef(atualizar);
  useEffect(() => {
    atualizarRef.current = atualizar;
  }, [atualizar]);

  const timerBusca = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (timerBusca.current !== null) {
      clearTimeout(timerBusca.current);
      timerBusca.current = null;
    }
  }, [filtros.q]);

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
    queryKey: ['aluno-catalogo', alunoId, filtros],
    queryFn: async () => {
      const bruto = await api.listarCatalogoAluno(alunoId, {
        pagina: filtros.pagina,
        tamanho_pagina: LIMITES.paginaPadrao,
        q: filtros.q,
        formato: filtros.formato,
        ordenar: 'criado_em:desc',
      });
      const analisado = PaginaCatalogoAlunoSchema.safeParse(bruto);
      if (!analisado.success) {
        throw new ErroContrato(analisado.error.issues.map((i) => i.message).join('; '));
      }
      return analisado.data;
    },
    enabled: Boolean(alunoId),
    staleTime: 30_000,
    retry: false,
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
