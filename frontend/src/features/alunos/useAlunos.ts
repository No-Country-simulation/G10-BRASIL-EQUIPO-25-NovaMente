'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useRouter, useSearchParams } from 'next/navigation';
import { useCallback, useEffect, useMemo, useRef } from 'react';
import { useApi } from '@/services/api/ApiProvider';
import { ErroContrato } from '@/services/api/erros';
import type { ListarAlunosParams } from '@/services/api/NovaMenteApi';
import {
  AlunoResumoSchema,
  LIMITES,
  PaginaAlunosSchema,
  statusAlunoSchema,
} from '@/types/schemas';
import type {
  AlunoAtualizacao,
  AlunoCriacao,
  AlunoResumo,
  StatusAluno,
} from '@/types/novamente';
import { ROTAS } from '@/lib/rotas';

export type OrdenacaoAlunos = NonNullable<ListarAlunosParams['ordenar']>;

export const ORDENACOES_ALUNOS: OrdenacaoAlunos[] = [
  'nome:asc',
  'nome:desc',
  'criado_em:desc',
];

const ORDENACAO_PADRAO: OrdenacaoAlunos = 'nome:asc';

export interface FiltrosAlunos {
  pagina: number;
  q: string;
  status?: StatusAluno;
  ordenar: OrdenacaoAlunos;
}

function lerPagina(valor: string | null): number {
  const numero = Number.parseInt(valor ?? '1', 10);
  return Number.isFinite(numero) && numero >= 1 ? numero : 1;
}

function lerStatus(valor: string | null): StatusAluno | undefined {
  if (!valor) return undefined;
  const analisado = statusAlunoSchema.safeParse(valor);
  return analisado.success ? analisado.data : undefined;
}

function lerOrdenacao(valor: string | null): OrdenacaoAlunos {
  if (!valor) return ORDENACAO_PADRAO;
  return ORDENACOES_ALUNOS.includes(valor as OrdenacaoAlunos)
    ? (valor as OrdenacaoAlunos)
    : ORDENACAO_PADRAO;
}

function validarAluno(bruto: unknown): AlunoResumo {
  const analisado = AlunoResumoSchema.safeParse(bruto);
  if (!analisado.success) {
    throw new ErroContrato(analisado.error.issues.map((i) => i.message).join('; '));
  }
  return analisado.data;
}

export function useAlunos() {
  const api = useApi();
  const router = useRouter();
  const params = useSearchParams();

  const filtros = useMemo<FiltrosAlunos>(
    () => ({
      pagina: lerPagina(params.get('pagina')),
      q: params.get('q') ?? '',
      status: lerStatus(params.get('status')),
      ordenar: lerOrdenacao(params.get('ordenar')),
    }),
    [params],
  );

  const atualizar = useCallback(
    (mudanca: Partial<FiltrosAlunos>) => {
      const proximos: FiltrosAlunos = { ...filtros, ...mudanca };
      const busca = new URLSearchParams();
      if (proximos.pagina > 1) busca.set('pagina', String(proximos.pagina));
      if (proximos.status) busca.set('status', proximos.status);
      if (proximos.ordenar !== ORDENACAO_PADRAO) busca.set('ordenar', proximos.ordenar);
      if (proximos.q.trim()) busca.set('q', proximos.q.trim());
      const query = busca.toString();
      router.replace(query ? `${ROTAS.empresaAlunos}?${query}` : ROTAS.empresaAlunos);
    },
    [filtros, router],
  );

  // A busca precisa enxergar os filtros mais recentes mesmo quando o usuário
  // troca um filtro durante a janela de debounce.
  const atualizarRef = useRef(atualizar);
  useEffect(() => {
    atualizarRef.current = atualizar;
  }, [atualizar]);

  const timerBusca = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Mudança externa da URL (voltar/avançar) invalida o commit pendente para
  // não sobrescrever o que a navegação acabou de restaurar.
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
    queryKey: ['alunos', filtros],
    queryFn: async () => {
      const bruto = await api.listarAlunos({
        pagina: filtros.pagina,
        tamanho_pagina: LIMITES.paginaPadrao,
        q: filtros.q,
        status: filtros.status,
        ordenar: filtros.ordenar,
      });
      const analisado = PaginaAlunosSchema.safeParse(bruto);
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

export function useAluno(alunoId: string) {
  const api = useApi();

  return useQuery({
    queryKey: ['aluno', alunoId],
    queryFn: async () => {
      const bruto = await api.obterAluno(alunoId);
      return validarAluno(bruto);
    },
    enabled: Boolean(alunoId),
    staleTime: 30_000,
    retry: false,
  });
}

export function useCriarAluno() {
  const api = useApi();
  const queryClient = useQueryClient();

  return useMutation<AlunoResumo, unknown, AlunoCriacao>({
    mutationFn: async (dados) => {
      const bruto = await api.criarAluno(dados);
      return validarAluno(bruto);
    },
    onSuccess: (criado) => {
      queryClient.setQueryData<AlunoResumo>(['aluno', criado.aluno_id], criado);
      queryClient.invalidateQueries({ queryKey: ['alunos'] });
      queryClient.invalidateQueries({
        queryKey: ['aluno', criado.aluno_id],
        refetchType: 'none',
      });
      queryClient.invalidateQueries({ queryKey: ['vinculos', criado.aluno_id] });
    },
  });
}

interface AtualizacaoAluno {
  alunoId: string;
  dados: AlunoAtualizacao;
}

export function useAtualizarAluno() {
  const api = useApi();
  const queryClient = useQueryClient();

  return useMutation<AlunoResumo, unknown, AtualizacaoAluno>({
    mutationFn: async ({ alunoId, dados }) => {
      const bruto = await api.atualizarAluno(alunoId, dados);
      return validarAluno(bruto);
    },
    onSuccess: (atualizado, { alunoId }) => {
      queryClient.setQueryData<AlunoResumo>(['aluno', alunoId], atualizado);
      queryClient.invalidateQueries({ queryKey: ['alunos'] });
      queryClient.invalidateQueries({ queryKey: ['aluno', alunoId], refetchType: 'none' });
      queryClient.invalidateQueries({ queryKey: ['vinculos', alunoId] });
    },
  });
}

export function useExcluirAluno() {
  const api = useApi();
  const queryClient = useQueryClient();

  return useMutation<void, unknown, string>({
    mutationFn: (alunoId) => api.excluirAluno(alunoId),
    onSuccess: (_resultado, alunoId) => {
      queryClient.invalidateQueries({ queryKey: ['alunos'] });
      queryClient.invalidateQueries({ queryKey: ['aluno', alunoId] });
      queryClient.invalidateQueries({ queryKey: ['vinculos', alunoId] });
    },
  });
}
