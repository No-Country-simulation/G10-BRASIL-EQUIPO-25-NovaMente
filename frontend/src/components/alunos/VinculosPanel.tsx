'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import { AlertTriangle } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import {
  ErroAplicarVinculos,
  useAplicarVinculos,
  useVinculos,
  type DiferencaVinculos,
} from '@/features/alunos/useVinculos';
import { useMateriais } from '@/features/materiais/useMateriais';
import { FORMATOS } from '@/lib/constants';
import { mensagemDoErro } from '@/services/api/erros';
import { M } from '@/lib/mensagens';
import { ROTAS } from '@/lib/rotas';
import type { FormatoSaida, MaterialResumo } from '@/types/novamente';

const ROTULOS_FORMATO = Object.fromEntries(
  FORMATOS.map((formato) => [formato.valor, formato.rotulo]),
) as Record<FormatoSaida, string>;

export interface VinculosPanelProps {
  alunoId: string;
  /** Injeta a mutation nos testes; em produção usa `useAplicarVinculos`. */
  aplicar?: (diferenca: DiferencaVinculos) => Promise<void>;
  onAlteracoesPendentes?: (pendentes: boolean) => void;
}

export function VinculosPanel({
  alunoId,
  aplicar,
  onAlteracoesPendentes,
}: VinculosPanelProps) {
  const materiaisQuery = useMateriais({ filtrosLocais: true });
  const vinculosQuery = useVinculos(alunoId);
  const aplicarVinculos = useAplicarVinculos(alunoId);
  const aplicarPadrao = aplicar ?? aplicarVinculos.mutateAsync;

  const [alteracoes, setAlteracoes] = useState<Record<string, boolean>>({});
  const [salvando, setSalvando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);

  const vinculados = useMemo(
    () => new Set((vinculosQuery.data?.itens ?? []).map((item) => item.material_id)),
    [vinculosQuery.data],
  );

  const titulos = useMemo(() => {
    const mapa = new Map<string, string>();
    for (const item of vinculosQuery.data?.itens ?? []) mapa.set(item.material_id, item.titulo);
    for (const item of materiaisQuery.data?.itens ?? []) mapa.set(item.material_id, item.titulo);
    return mapa;
  }, [vinculosQuery.data, materiaisQuery.data]);

  const pendentes = Object.keys(alteracoes).length > 0;

  useEffect(() => {
    onAlteracoesPendentes?.(pendentes);
  }, [onAlteracoesPendentes, pendentes]);

  useEffect(() => {
    if (!pendentes) return;
    const avisarSaida = (evento: BeforeUnloadEvent) => {
      evento.preventDefault();
      evento.returnValue = '';
    };
    window.addEventListener('beforeunload', avisarSaida);
    return () => window.removeEventListener('beforeunload', avisarSaida);
  }, [pendentes]);

  const campoBusca = useRef<HTMLInputElement>(null);
  useEffect(() => {
    const campo = campoBusca.current;
    if (campo && campo.value !== materiaisQuery.busca) campo.value = materiaisQuery.busca;
  }, [materiaisQuery.busca]);

  const marcado = (materialId: string) =>
    Object.prototype.hasOwnProperty.call(alteracoes, materialId)
      ? alteracoes[materialId]
      : vinculados.has(materialId);

  const alternar = (material: MaterialResumo) => {
    const materialId = material.material_id;
    setAlteracoes((atuais) => {
      const base = vinculados.has(materialId);
      const atual = Object.prototype.hasOwnProperty.call(atuais, materialId)
        ? atuais[materialId]
        : base;
      const desejado = !atual;
      const proximos = { ...atuais };
      if (desejado === base) delete proximos[materialId];
      else proximos[materialId] = desejado;
      return proximos;
    });
    setErro(null);
    setAviso(null);
  };

  const diferenca = useMemo<DiferencaVinculos>(() => {
    const adicionar: string[] = [];
    const remover: string[] = [];
    for (const [materialId, selecionado] of Object.entries(alteracoes)) {
      if (selecionado) adicionar.push(materialId);
      else remover.push(materialId);
    }
    return { adicionar, remover };
  }, [alteracoes]);

  const salvar = async () => {
    if (diferenca.adicionar.length === 0 && diferenca.remover.length === 0) return;
    setErro(null);
    setAviso(null);
    setSalvando(true);
    try {
      await aplicarPadrao(diferenca);
      setAlteracoes({});
      setAviso(M.alunos.vinculosSalvos);
    } catch (falha) {
      const resultados = await Promise.allSettled([
        vinculosQuery.refetch(),
        materiaisQuery.refetch(),
      ]);
      const resultadoVinculos = resultados[0];
      if (resultadoVinculos.status === 'fulfilled' && resultadoVinculos.value.data) {
        const vinculadosAtualizados = new Set(
          resultadoVinculos.value.data.itens.map((item) => item.material_id),
        );
        // Mantém apenas o que continua divergindo do servidor: operações que
        // tiveram sucesso já foram refletidas pelo refetch.
        setAlteracoes((atuais) => {
          const proximos: Record<string, boolean> = {};
          for (const [materialId, selecionado] of Object.entries(atuais)) {
            if (vinculadosAtualizados.has(materialId) !== selecionado) {
              proximos[materialId] = selecionado;
            }
          }
          return proximos;
        });
      }
      if (falha instanceof ErroAplicarVinculos) {
        const nomes = [
          ...new Set(falha.falhas.map((item) => titulos.get(item.materialId) ?? item.materialId)),
        ];
        setErro(M.alunos.vinculosFalha(nomes.join(', ')));
      } else {
        setErro(mensagemDoErro(falha));
      }
    } finally {
      setSalvando(false);
    }
  };

  const carregando = materiaisQuery.isLoading || vinculosQuery.isLoading;
  const erroConsulta = materiaisQuery.error ?? vinculosQuery.error;
  const dadosMateriais = materiaisQuery.data;
  const temFiltros = Boolean(materiaisQuery.filtros.q || materiaisQuery.filtros.formato);

  return (
    <section className="space-y-4" aria-labelledby="vinculos-titulo">
      <div>
        <h2 id="vinculos-titulo" className="text-lg font-semibold">
          {M.alunos.vinculosTitulo}
        </h2>
        <p className="text-sm text-[var(--fg-muted)]">{M.alunos.vinculosDescricao}</p>
      </div>

      <div className="flex flex-wrap gap-3">
        <label className="sr-only" htmlFor="vinculos-busca">
          {M.alunos.vinculosBusca}
        </label>
        <input
          ref={campoBusca}
          id="vinculos-busca"
          type="search"
          defaultValue={materiaisQuery.busca}
          placeholder={M.alunos.vinculosBuscaPlaceholder}
          onChange={(evento) => materiaisQuery.setBusca(evento.target.value)}
          className="h-10 min-w-[220px] flex-1 rounded-md border bg-[var(--surface)] px-3 text-sm"
        />

        <label className="sr-only" htmlFor="vinculos-formato">
          {M.alunos.vinculosTodosFormatos}
        </label>
        <select
          id="vinculos-formato"
          value={materiaisQuery.filtros.formato ?? ''}
          onChange={(evento) =>
            materiaisQuery.atualizar({
              formato: (evento.target.value || undefined) as FormatoSaida | undefined,
              pagina: 1,
            })
          }
          className="h-10 rounded-md border bg-[var(--surface)] px-3 text-sm"
        >
          <option value="">{M.alunos.vinculosTodosFormatos}</option>
          {FORMATOS.map((formato) => (
            <option key={formato.valor} value={formato.valor}>
              {formato.rotulo}
            </option>
          ))}
        </select>
      </div>

      {aviso && (
        <div
          role="status"
          aria-live="polite"
          className="rounded-lg border border-[var(--accent)] px-4 py-3 text-sm"
        >
          {aviso}
        </div>
      )}

      {erro && (
        <p role="alert" className="rounded-lg border border-[var(--danger)] px-4 py-3 text-sm text-[var(--danger)]">
          {erro}
        </p>
      )}

      {carregando && (
        <div className="space-y-2" aria-busy="true" aria-label={M.comum.carregando}>
          {Array.from({ length: 3 }).map((_, indice) => (
            <Skeleton key={indice} className="h-14 w-full" />
          ))}
        </div>
      )}

      {erroConsulta && !carregando && (
        <div role="alert" className="rounded-xl border border-[var(--danger)] p-6">
          <p className="flex items-center gap-2 text-[var(--danger)]">
            <AlertTriangle aria-hidden className="h-5 w-5" />
            {mensagemDoErro(erroConsulta)}
          </p>
          <Button
            className="mt-4"
            onClick={() => {
              void materiaisQuery.refetch();
              void vinculosQuery.refetch();
            }}
          >
            {M.comum.tentarNovamente}
          </Button>
        </div>
      )}

      {!carregando && !erroConsulta && dadosMateriais && (
        <>
          {dadosMateriais.itens.length === 0 && temFiltros && (
            <div className="rounded-xl border border-dashed p-8 text-center">
              <p className="text-[var(--fg-muted)]">{M.alunos.vinculosVazioFiltros}</p>
              <Button
                variant="outline"
                className="mt-4"
                onClick={() =>
                  materiaisQuery.atualizar({ q: '', formato: undefined, pagina: 1 })
                }
              >
                {M.alunos.vinculosLimparFiltros}
              </Button>
            </div>
          )}

          {dadosMateriais.itens.length === 0 && !temFiltros && (
            <div className="rounded-xl border border-dashed p-8 text-center">
              <p className="text-[var(--fg-muted)]">{M.alunos.vinculosVazio}</p>
              <Button asChild className="mt-4">
                <Link href={ROTAS.empresaGerar}>{M.alunos.vinculosVazioCta}</Link>
              </Button>
            </div>
          )}

          {dadosMateriais.itens.length > 0 && (
            <ul className="space-y-2">
              {dadosMateriais.itens.map((material) => (
                <li
                  key={material.material_id}
                  className="flex flex-wrap items-center gap-3 rounded-lg border p-3"
                >
                  <input
                    id={`vinculo-${material.material_id}`}
                    type="checkbox"
                    checked={marcado(material.material_id)}
                    onChange={() => alternar(material)}
                    aria-label={M.alunos.vinculosSelecionar(material.titulo)}
                    className="h-4 w-4 accent-[var(--accent)]"
                  />
                  <label
                    htmlFor={`vinculo-${material.material_id}`}
                    className="min-w-0 flex-1 text-sm font-medium"
                  >
                    {material.titulo}
                  </label>
                  <Badge variant="outline">{ROTULOS_FORMATO[material.formato]}</Badge>
                  <Badge variant={material.visibilidade === 'publicado' ? 'secondary' : 'outline'}>
                    {material.visibilidade === 'publicado'
                      ? M.materiais.publicado
                      : M.materiais.rascunho}
                  </Badge>
                </li>
              ))}
            </ul>
          )}

          {dadosMateriais.total > 0 && (
            <nav
              aria-label={M.alunos.vinculosPaginacao}
              className="flex items-center justify-center gap-3"
            >
              <Button
                variant="outline"
                disabled={dadosMateriais.pagina <= 1}
                onClick={() => materiaisQuery.atualizar({ pagina: dadosMateriais.pagina - 1 })}
              >
                {M.alunos.anterior}
              </Button>
              <span className="text-sm text-[var(--fg-muted)]">
                {M.alunos.vinculosPagina(
                  dadosMateriais.pagina,
                  dadosMateriais.total_paginas,
                )}
              </span>
              <Button
                variant="outline"
                disabled={dadosMateriais.pagina >= dadosMateriais.total_paginas}
                onClick={() => materiaisQuery.atualizar({ pagina: dadosMateriais.pagina + 1 })}
              >
                {M.alunos.proxima}
              </Button>
            </nav>
          )}
        </>
      )}

      <div className="flex flex-wrap items-center gap-3">
        <Button onClick={salvar} disabled={salvando || !pendentes}>
          {salvando ? M.alunos.vinculosSalvando : M.alunos.vinculosSalvar}
        </Button>
        {pendentes && (
          <p className="text-sm text-[var(--fg-muted)]">{M.alunos.vinculosPendentes}</p>
        )}
      </div>
    </section>
  );
}
