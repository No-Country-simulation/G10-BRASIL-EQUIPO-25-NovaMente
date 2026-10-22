'use client';

import Link from 'next/link';
import { useEffect, useRef } from 'react';
import { AlertTriangle } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { useAdaptationHistory } from '@/features/adaptations/useAdaptationHistory';
import { FORMATOS, PERFIS } from '@/lib/constants';
import { formatarDataRelativa, formatarPercentual } from '@/lib/formatadores';
import { mensagemDoErro } from '@/services/api/erros';
import { M } from '@/lib/mensagens';

export function HistoricoSkeleton() {
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3" aria-busy="true" aria-label={M.comum.carregando}>
      {Array.from({ length: 6 }).map((_, i) => (
        <Skeleton key={i} className="h-[180px] w-full" />
      ))}
    </div>
  );
}

export function HistoricoView() {
  const { data, isLoading, error, refetch, filtros, busca, setBusca, atualizar } = useAdaptationHistory();
  const campoBusca = useRef<HTMLInputElement>(null);
  const temFiltros = Boolean(filtros.q || filtros.formato || filtros.perfil);

  // O input é não-controlado para preservar o cursor e o foco enquanto o
  // debounce não confirma a busca na URL; a URL continua sendo a fonte de
  // verdade e reescreve o campo quando muda por navegação (voltar/avançar).
  useEffect(() => {
    const campo = campoBusca.current;
    if (campo && campo.value !== busca) campo.value = busca;
  }, [busca]);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">{M.historico.titulo}</h1>

      <div className="flex flex-wrap gap-3">
        <label className="sr-only" htmlFor="busca">
          {M.historico.busca}
        </label>
        <input
          ref={campoBusca}
          id="busca"
          type="search"
          defaultValue={busca}
          placeholder={M.historico.busca}
          onChange={(e) => setBusca(e.target.value)}
          className="h-10 min-w-[240px] flex-1 rounded-md border bg-[var(--surface)] px-3 text-sm"
        />

        <label className="sr-only" htmlFor="filtro-formato">
          {M.historico.todosFormatos}
        </label>
        <select
          id="filtro-formato"
          value={filtros.formato ?? ''}
          onChange={(e) => atualizar({ formato: e.target.value || undefined, pagina: 1 })}
          className="h-10 rounded-md border bg-[var(--surface)] px-3 text-sm"
        >
          <option value="">{M.historico.todosFormatos}</option>
          {FORMATOS.map((f) => (
            <option key={f.valor} value={f.valor}>
              {f.rotulo}
            </option>
          ))}
        </select>

        <label className="sr-only" htmlFor="filtro-perfil">
          {M.historico.todosPerfis}
        </label>
        <select
          id="filtro-perfil"
          value={filtros.perfil ?? ''}
          onChange={(e) => atualizar({ perfil: e.target.value || undefined, pagina: 1 })}
          className="h-10 rounded-md border bg-[var(--surface)] px-3 text-sm"
        >
          <option value="">{M.historico.todosPerfis}</option>
          {PERFIS.map((p) => (
            <option key={p.valor} value={p.valor}>
              {p.rotulo}
            </option>
          ))}
        </select>
      </div>

      {isLoading && <HistoricoSkeleton />}

      {error && (
        <div role="alert" className="rounded-xl border border-[var(--danger)] p-6">
          <p className="flex items-center gap-2 text-[var(--danger)]">
            <AlertTriangle aria-hidden className="h-5 w-5" />
            {mensagemDoErro(error)}
          </p>
          <Button className="mt-4" onClick={() => refetch()}>
            {M.comum.tentarNovamente}
          </Button>
        </div>
      )}

      {data && data.itens.length === 0 && !error && data.total === 0 && temFiltros && (
        <div className="rounded-xl border border-dashed p-10 text-center">
          <p className="text-[var(--fg-muted)]">{M.historico.vazioFiltros}</p>
          <Button
            variant="outline"
            className="mt-4"
            onClick={() => atualizar({ q: '', formato: undefined, perfil: undefined, pagina: 1 })}
          >
            {M.historico.limparFiltros}
          </Button>
        </div>
      )}

      {data && data.itens.length === 0 && !error && data.total === 0 && !temFiltros && (
        <div className="rounded-xl border border-dashed p-10 text-center">
          <p className="text-[var(--fg-muted)]">{M.historico.vazio}</p>
          <Button asChild className="mt-4">
            <Link href="/">{M.historico.vazioCta}</Link>
          </Button>
        </div>
      )}

      {data && data.itens.length > 0 && (
        <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {data.itens.map((item) => (
            <li key={item.adaptacao_id}>
              <Link
                href={`/resultado/${item.adaptacao_id}`}
                className="block h-full rounded-xl border p-5 transition-colors hover:border-[var(--accent)]"
              >
                <p className="font-medium">{item.documento.titulo}</p>
                <p className="mt-1 text-xs text-[var(--fg-muted)]">
                  {formatarDataRelativa(item.criado_em)}
                </p>
                <div className="mt-3 flex flex-wrap gap-2">
                  <Badge>{item.formato_gerado}</Badge>
                  <Badge variant="secondary">{item.perfil_aplicado}</Badge>
                  {item.status_upload === 'falha' && <Badge variant="destructive">{M.oci.falhaUpload}</Badge>}
                </div>
                <p className="mt-3 text-sm text-[var(--fg-muted)]">
                  {M.resultado.ancoragem}: {formatarPercentual(item.ancoragem_fonte_score)}
                </p>
              </Link>
            </li>
          ))}
        </ul>
      )}

      {/* A paginação depende do total, não da página atual: numa página fora
          do intervalo a lista vem vazia, mas o usuário ainda precisa navegar. */}
      {data && data.total > 0 && (
        <nav aria-label={M.historico.paginacao} className="flex items-center justify-center gap-3">
          <Button
            variant="outline"
            disabled={data.pagina <= 1}
            onClick={() => atualizar({ pagina: data.pagina - 1 })}
          >
            {M.historico.anterior}
          </Button>
          <span className="text-sm text-[var(--fg-muted)]">
            {M.historico.pagina(data.pagina, data.total_paginas)}
          </span>
          <Button
            variant="outline"
            disabled={data.pagina >= data.total_paginas}
            onClick={() => atualizar({ pagina: data.pagina + 1 })}
          >
            {M.historico.proxima}
          </Button>
        </nav>
      )}
    </div>
  );
}
