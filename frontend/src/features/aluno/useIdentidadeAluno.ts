'use client';

import { useCallback, useMemo, useSyncExternalStore } from 'react';
import { useQuery } from '@tanstack/react-query';
import { z } from 'zod';
import { useApi } from '@/services/api/ApiProvider';
import { ErroContrato } from '@/services/api/erros';
import { IdentificacaoAlunoItemSchema } from '@/types/schemas';
import type { IdentificacaoAlunoItem } from '@/types/novamente';

export const CHAVE_IDENTIDADE_ALUNO = 'novamente.aluno';

const IdentidadeAlunoSchema = z
  .object({
    aluno_id: z.string().min(1),
    nome: z.string().min(1),
  })
  .strict();

export type IdentidadeAluno = z.infer<typeof IdentidadeAlunoSchema>;

const ouvintes = new Set<() => void>();

function lerBruto(): string {
  if (typeof window === 'undefined') return '';
  return window.localStorage.getItem(CHAVE_IDENTIDADE_ALUNO) ?? '';
}

function assinar(ouvinte: () => void) {
  ouvintes.add(ouvinte);
  if (typeof window === 'undefined') return () => ouvintes.delete(ouvinte);

  const aoMudarArmazenamento = (evento: StorageEvent) => {
    if (evento.key === CHAVE_IDENTIDADE_ALUNO || evento.key === null) ouvinte();
  };
  window.addEventListener('storage', aoMudarArmazenamento);
  return () => {
    ouvintes.delete(ouvinte);
    window.removeEventListener('storage', aoMudarArmazenamento);
  };
}

function notificar() {
  for (const ouvinte of ouvintes) ouvinte();
}

function analisarIdentidade(bruto: string): IdentidadeAluno | null {
  if (!bruto) return null;
  try {
    const analisado = IdentidadeAlunoSchema.safeParse(JSON.parse(bruto));
    return analisado.success ? analisado.data : null;
  } catch {
    return null;
  }
}

function gravar(identidade: IdentidadeAluno | null) {
  if (typeof window === 'undefined') return;
  if (identidade) {
    window.localStorage.setItem(CHAVE_IDENTIDADE_ALUNO, JSON.stringify(identidade));
  } else {
    window.localStorage.removeItem(CHAVE_IDENTIDADE_ALUNO);
  }
  notificar();
}

/**
 * Identidade leve do aluno, compartilhada por todas as telas via
 * `localStorage['novamente.aluno']`. Não é autenticação: guarda apenas o id e o
 * nome escolhidos na identificação.
 */
export function useIdentidadeAluno() {
  const bruto = useSyncExternalStore(assinar, lerBruto, () => '');
  const aluno = useMemo(() => analisarIdentidade(bruto), [bruto]);

  const identificar = useCallback((item: IdentificacaoAlunoItem) => {
    gravar({ aluno_id: item.aluno_id, nome: item.nome });
  }, []);

  const limpar = useCallback(() => {
    gravar(null);
  }, []);

  return {
    aluno,
    identificar,
    trocarAluno: limpar,
    limpar,
  };
}

/** Lista de alunos ativos para a identificação, sem e-mail (contrato da API). */
export function useIdentificacaoAluno() {
  const api = useApi();

  return useQuery({
    queryKey: ['aluno-identificacao'],
    queryFn: async () => {
      const bruto = await api.listarIdentificacaoAluno();
      const analisado = z.array(IdentificacaoAlunoItemSchema).safeParse(bruto);
      if (!analisado.success) {
        throw new ErroContrato(analisado.error.issues.map((i) => i.message).join('; '));
      }
      return analisado.data;
    },
    staleTime: 30_000,
    retry: false,
  });
}
