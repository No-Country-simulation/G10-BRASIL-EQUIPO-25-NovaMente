'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useRouter, useSearchParams } from 'next/navigation';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useApi } from '@/services/api/ApiProvider';
import { ErroContrato } from '@/services/api/erros';
import type { ListarMateriaisParams } from '@/services/api/NovaMenteApi';
import {
  formatoSaidaSchema,
  LIMITES,
  MaterialResumoSchema,
  PaginaMateriaisSchema,
  perfilSchema,
  RemocaoMaterialRespostaSchema,
  visibilidadeMaterialSchema,
} from '@/types/schemas';
import type {
  FormatoSaida,
  MaterialAtualizacao,
  MaterialDetalhe,
  MaterialResumo,
  PaginaMateriais,
  PerfilDestinatario,
  RemocaoMaterialResposta,
  VisibilidadeMaterial,
} from '@/types/novamente';
import { ROTAS } from '@/lib/rotas';

export type OrdenacaoMateriais = NonNullable<ListarMateriaisParams['ordenar']>;

export const ORDENACOES_MATERIAIS: OrdenacaoMateriais[] = [
  'criado_em:desc',
  'criado_em:asc',
  'ancoragem:desc',
  'titulo:asc',
];

const ORDENACAO_PADRAO: OrdenacaoMateriais = 'criado_em:desc';

export interface FiltrosMateriais {
  pagina: number;
  q: string;
  formato?: FormatoSaida;
  perfil?: PerfilDestinatario;
  visibilidade?: VisibilidadeMaterial;
  ordenar: OrdenacaoMateriais;
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

function lerPerfil(valor: string | null): PerfilDestinatario | undefined {
  if (!valor) return undefined;
  const analisado = perfilSchema.safeParse(valor);
  return analisado.success ? analisado.data : undefined;
}

function lerVisibilidade(valor: string | null): VisibilidadeMaterial | undefined {
  if (!valor) return undefined;
  const analisado = visibilidadeMaterialSchema.safeParse(valor);
  return analisado.success ? analisado.data : undefined;
}

function lerOrdenacao(valor: string | null): OrdenacaoMateriais {
  if (!valor) return ORDENACAO_PADRAO;
  return ORDENACOES_MATERIAIS.includes(valor as OrdenacaoMateriais)
    ? (valor as OrdenacaoMateriais)
    : ORDENACAO_PADRAO;
}

function validarResumo(bruto: unknown): MaterialResumo {
  const analisado = MaterialResumoSchema.safeParse(bruto);
  if (!analisado.success) {
    throw new ErroContrato(analisado.error.issues.map((i) => i.message).join('; '));
  }
  return analisado.data;
}

export interface OpcoesMateriais {
  /**
   * Mantém os filtros apenas em memória em vez de espelhá-los na URL. Usado
   * em telas que embutem a listagem sem serem a rota de materiais.
   */
  filtrosLocais?: boolean;
}

const FILTROS_LOCAIS_INICIAIS: FiltrosMateriais = {
  pagina: 1,
  q: '',
  ordenar: ORDENACAO_PADRAO,
};

export function useMateriais(opcoes: OpcoesMateriais = {}) {
  const api = useApi();
  const router = useRouter();
  const params = useSearchParams();
  const filtrosLocais = opcoes.filtrosLocais ?? false;
  const [filtrosEmMemoria, setFiltrosEmMemoria] =
    useState<FiltrosMateriais>(FILTROS_LOCAIS_INICIAIS);

  const filtrosDaUrl = useMemo<FiltrosMateriais>(
    () => ({
      pagina: lerPagina(params.get('pagina')),
      q: params.get('q') ?? '',
      formato: lerFormato(params.get('formato')),
      perfil: lerPerfil(params.get('perfil')),
      visibilidade: lerVisibilidade(params.get('visibilidade')),
      ordenar: lerOrdenacao(params.get('ordenar')),
    }),
    [params],
  );

  const filtros = filtrosLocais ? filtrosEmMemoria : filtrosDaUrl;

  const atualizar = useCallback(
    (mudanca: Partial<FiltrosMateriais>) => {
      const proximos: FiltrosMateriais = { ...filtros, ...mudanca };
      if (filtrosLocais) {
        setFiltrosEmMemoria(proximos);
        return;
      }
      const busca = new URLSearchParams();
      if (proximos.pagina > 1) busca.set('pagina', String(proximos.pagina));
      if (proximos.formato) busca.set('formato', proximos.formato);
      if (proximos.perfil) busca.set('perfil', proximos.perfil);
      if (proximos.visibilidade) busca.set('visibilidade', proximos.visibilidade);
      if (proximos.ordenar !== ORDENACAO_PADRAO) busca.set('ordenar', proximos.ordenar);
      if (proximos.q.trim()) busca.set('q', proximos.q.trim());
      const query = busca.toString();
      router.replace(query ? `${ROTAS.empresaMateriais}?${query}` : ROTAS.empresaMateriais);
    },
    [filtros, filtrosLocais, router],
  );

  // O timer de busca precisa enxergar os filtros mais recentes mesmo quando o
  // usuário troca um filtro durante a janela de debounce.
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
    queryKey: ['materiais', filtros],
    queryFn: async () => {
      const bruto = await api.listarMateriais({
        pagina: filtros.pagina,
        tamanho_pagina: LIMITES.paginaPadrao,
        q: filtros.q,
        formato: filtros.formato,
        perfil: filtros.perfil,
        visibilidade: filtros.visibilidade,
        ordenar: filtros.ordenar,
      });
      const analisado = PaginaMateriaisSchema.safeParse(bruto);
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

interface AtualizacaoMaterial {
  materialId: string;
  dados: MaterialAtualizacao;
}

interface ContextoAtualizacao {
  listas: [readonly unknown[], PaginaMateriais | undefined][];
  detalhe: MaterialDetalhe | undefined;
}

function aplicarNoMaterial(material: MaterialResumo, dados: MaterialAtualizacao): MaterialResumo {
  return {
    ...material,
    ...(dados.titulo !== undefined ? { titulo: dados.titulo } : {}),
    ...(dados.visibilidade !== undefined ? { visibilidade: dados.visibilidade } : {}),
  };
}

function aplicarNaPagina(
  pagina: PaginaMateriais | undefined,
  materialId: string,
  dados: MaterialAtualizacao,
): PaginaMateriais | undefined {
  if (!pagina) return pagina;
  return {
    ...pagina,
    itens: pagina.itens.map((item) =>
      item.material_id === materialId ? aplicarNoMaterial(item, dados) : item,
    ),
  };
}

export function useAtualizarMaterial() {
  const api = useApi();
  const queryClient = useQueryClient();

  return useMutation<MaterialResumo, unknown, AtualizacaoMaterial, ContextoAtualizacao>({
    mutationFn: async ({ materialId, dados }) => {
      const bruto = await api.atualizarMaterial(materialId, dados);
      return validarResumo(bruto);
    },
    onMutate: async ({ materialId, dados }) => {
      await queryClient.cancelQueries({ queryKey: ['materiais'] });
      const listas = queryClient.getQueriesData<PaginaMateriais>({ queryKey: ['materiais'] });
      queryClient.setQueriesData<PaginaMateriais>({ queryKey: ['materiais'] }, (pagina) =>
        aplicarNaPagina(pagina, materialId, dados),
      );
      const detalhe = queryClient.getQueryData<MaterialDetalhe>(['material', materialId]);
      if (detalhe) {
        queryClient.setQueryData<MaterialDetalhe>(['material', materialId], {
          ...detalhe,
          material: aplicarNoMaterial(detalhe.material, dados),
        });
      }
      return { listas, detalhe };
    },
    onError: (_erro, _variavel, contexto) => {
      for (const [chave, pagina] of contexto?.listas ?? []) {
        queryClient.setQueryData(chave, pagina);
      }
      if (contexto?.detalhe) {
        queryClient.setQueryData(['material', contexto.detalhe.material.material_id], contexto.detalhe);
      }
    },
    onSuccess: (atualizado, { materialId }) => {
      queryClient.setQueryData<MaterialDetalhe>(['material', materialId], (antigo) =>
        antigo ? { ...antigo, material: atualizado } : antigo,
      );
      queryClient.invalidateQueries({ queryKey: ['materiais'] });
      queryClient.invalidateQueries({ queryKey: ['material', materialId], refetchType: 'none' });
      queryClient.invalidateQueries({ queryKey: ['aluno-catalogo'] });
      queryClient.invalidateQueries({ queryKey: ['vinculos'] });
    },
  });
}

export function useExcluirMaterial() {
  const api = useApi();
  const queryClient = useQueryClient();

  return useMutation<RemocaoMaterialResposta, unknown, string>({
    mutationFn: async (materialId) => {
      const bruto = await api.excluirMaterial(materialId);
      const analisado = RemocaoMaterialRespostaSchema.safeParse(bruto);
      if (!analisado.success) {
        throw new ErroContrato(analisado.error.issues.map((i) => i.message).join('; '));
      }
      return analisado.data;
    },
    onSuccess: (_resultado, materialId) => {
      queryClient.invalidateQueries({ queryKey: ['materiais'] });
      queryClient.invalidateQueries({ queryKey: ['material', materialId] });
      queryClient.invalidateQueries({ queryKey: ['aluno-catalogo'] });
      queryClient.invalidateQueries({ queryKey: ['vinculos'] });
    },
  });
}

