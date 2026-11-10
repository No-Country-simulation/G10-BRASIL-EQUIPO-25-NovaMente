'use client';

import { useEffect, useRef } from 'react';
import Link from 'next/link';
import { AlertTriangle } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { useCatalogoAluno } from '@/features/aluno/useCatalogoAluno';
import type { IdentidadeAluno } from '@/features/aluno/useIdentidadeAluno';
import { FORMATOS, PERFIS } from '@/lib/constants';
import { M } from '@/lib/mensagens';
import { ROTAS } from '@/lib/rotas';
import { ErroApi, mensagemDoErro } from '@/services/api/erros';
import type { FormatoSaida, ItemCatalogoAluno } from '@/types/novamente';

const ROTULOS_FORMATO = Object.fromEntries(
  FORMATOS.map((formato) => [formato.valor, formato.rotulo]),
) as Record<FormatoSaida, string>;

const ROTULOS_PERFIL = Object.fromEntries(
  PERFIS.map((perfil) => [perfil.valor, perfil.rotulo]),
) as Record<ItemCatalogoAluno['perfil'], string>;

export function CatalogoAlunoSkeleton() {
  return (
    <div
      className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3"
      aria-busy="true"
      aria-label={M.aluno.catalogo.carregando}
    >
      {Array.from({ length: 6 }).map((_, indice) => (
        <Skeleton key={indice} className="h-[210px] w-full" />
      ))}
    </div>
  );
}

export interface CatalogoAlunoViewProps {
  aluno: IdentidadeAluno;
  /** Chamado quando o servidor nega a sessão (aluno inativo ou removido). */
  onSessaoInvalida: (mensagem: string) => void;
}

export function CatalogoAlunoView({ aluno, onSessaoInvalida }: CatalogoAlunoViewProps) {
  const consulta = useCatalogoAluno(aluno.aluno_id);
  const campoBusca = useRef<HTMLInputElement>(null);

  const erroSessao =
    consulta.error instanceof ErroApi &&
    (consulta.error.status === 403 || consulta.error.status === 404);

  useEffect(() => {
    if (erroSessao) onSessaoInvalida(M.aluno.catalogo.sessaoInvalida);
  }, [erroSessao, onSessaoInvalida]);

  useEffect(() => {
    const campo = campoBusca.current;
    if (campo && campo.value !== consulta.busca) campo.value = consulta.busca;
  }, [consulta.busca]);

  const temFiltros = Boolean(consulta.filtros.q || consulta.filtros.formato);
  const data = consulta.data;

  if (erroSessao) return <CatalogoAlunoSkeleton />;

  return (
    <div className="space-y-6" data-tour="aluno-catalogo">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold">{M.aluno.catalogo.saudacao(aluno.nome)}</h1>
        <p className="text-sm text-[var(--fg-muted)]">{M.aluno.catalogo.descricao}</p>
      </header>

      <div className="flex flex-wrap gap-3">
        <label className="sr-only" htmlFor="aluno-catalogo-busca">
          {M.aluno.catalogo.busca}
        </label>
        <input
          ref={campoBusca}
          id="aluno-catalogo-busca"
          type="search"
          defaultValue={consulta.busca}
          placeholder={M.aluno.catalogo.buscaPlaceholder}
          onChange={(evento) => consulta.setBusca(evento.target.value)}
          className="h-10 min-w-[240px] flex-1 rounded-md border bg-[var(--surface)] px-3 text-sm"
        />

        <label className="sr-only" htmlFor="aluno-catalogo-formato">
          {M.aluno.catalogo.todosFormatos}
        </label>
        <select
          id="aluno-catalogo-formato"
          value={consulta.filtros.formato ?? ''}
          onChange={(evento) =>
            consulta.atualizar({
              formato: (evento.target.value || undefined) as FormatoSaida | undefined,
              pagina: 1,
            })
          }
          className="h-10 rounded-md border bg-[var(--surface)] px-3 text-sm"
        >
          <option value="">{M.aluno.catalogo.todosFormatos}</option>
          {FORMATOS.map((formato) => (
            <option key={formato.valor} value={formato.valor}>
              {formato.rotulo}
            </option>
          ))}
        </select>
      </div>

      {consulta.isLoading && <CatalogoAlunoSkeleton />}

      {consulta.error && !erroSessao && (
        <div role="alert" className="rounded-xl border border-[var(--danger)] p-6">
          <p className="flex items-center gap-2 text-[var(--danger)]">
            <AlertTriangle aria-hidden className="h-5 w-5" />
            {mensagemDoErro(consulta.error)}
          </p>
          <Button className="mt-4" onClick={() => consulta.refetch()}>
            {M.comum.tentarNovamente}
          </Button>
        </div>
      )}

      {data && data.itens.length === 0 && !consulta.error && temFiltros && (
        <div className="rounded-xl border border-dashed p-10 text-center">
          <p className="text-[var(--fg-muted)]">{M.aluno.catalogo.vazioFiltros}</p>
          <Button
            variant="outline"
            className="mt-4"
            onClick={() => consulta.atualizar({ q: '', formato: undefined, pagina: 1 })}
          >
            {M.aluno.catalogo.limparFiltros}
          </Button>
        </div>
      )}

      {data && data.itens.length === 0 && !consulta.error && !temFiltros && (
        <div className="rounded-xl border border-dashed p-10 text-center">
          <p className="text-[var(--fg-muted)]">{M.aluno.catalogo.vazio}</p>
        </div>
      )}

      {data && data.itens.length > 0 && (
        <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {data.itens.map((item) => (
            <li key={item.material_id}>
              <article className="flex h-full flex-col rounded-xl border p-5 transition-colors hover:border-[var(--accent)]">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <h2 className="font-medium">
                      <Link
                        href={ROTAS.alunoMaterial(item.material_id)}
                        className="hover:underline"
                      >
                        {item.titulo}
                      </Link>
                    </h2>
                    <p className="mt-1 truncate text-sm text-[var(--fg-muted)]">
                      {item.documento_titulo}
                    </p>
                  </div>
                  <Badge>{ROTULOS_FORMATO[item.formato]}</Badge>
                </div>

                <div className="mt-3 flex flex-wrap items-center gap-2 text-sm text-[var(--fg-muted)]">
                  <Badge variant="secondary">{ROTULOS_PERFIL[item.perfil]}</Badge>
                  <span>{M.resultado.tempoEstimado(item.tempo_estimado_estudo_minutos)}</span>
                </div>

                {item.conceitos_chave.length > 0 && (
                  <ul
                    aria-label={M.aluno.catalogo.conceitos}
                    className="mt-3 flex flex-wrap gap-1"
                  >
                    {item.conceitos_chave.map((conceito) => (
                      <li key={conceito}>
                        <Badge variant="outline">{conceito}</Badge>
                      </li>
                    ))}
                  </ul>
                )}

                <div className="mt-auto pt-4">
                  <Button asChild variant="outline" size="sm">
                    <Link href={ROTAS.alunoMaterial(item.material_id)}>
                      {M.aluno.catalogo.estudar}
                    </Link>
                  </Button>
                </div>
              </article>
            </li>
          ))}
        </ul>
      )}

      {data && data.total > 0 && (
        <nav
          aria-label={M.aluno.catalogo.paginacao}
          className="flex items-center justify-center gap-3"
        >
          <Button
            variant="outline"
            disabled={data.pagina <= 1}
            onClick={() => consulta.atualizar({ pagina: data.pagina - 1 })}
          >
            {M.aluno.catalogo.anterior}
          </Button>
          <span className="text-sm text-[var(--fg-muted)]">
            {M.aluno.catalogo.pagina(data.pagina, data.total_paginas)}
          </span>
          <Button
            variant="outline"
            disabled={data.pagina >= data.total_paginas}
            onClick={() => consulta.atualizar({ pagina: data.pagina + 1 })}
          >
            {M.aluno.catalogo.proxima}
          </Button>
        </nav>
      )}
    </div>
  );
}
