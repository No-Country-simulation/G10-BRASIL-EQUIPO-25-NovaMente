'use client';

import { useEffect, useRef, useState } from 'react';
import { AlertTriangle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { AlunoCard } from './AlunoCard';
import { AlunoDeleteDialog } from './AlunoDeleteDialog';
import { AlunoFormDialog } from './AlunoFormDialog';
import {
  ORDENACOES_ALUNOS,
  useAlunos,
  useAtualizarAluno,
  useCriarAluno,
  useExcluirAluno,
} from '@/features/alunos/useAlunos';
import { mensagemDoErro } from '@/services/api/erros';
import { M } from '@/lib/mensagens';
import type { AlunoCriacao, AlunoResumo, StatusAluno } from '@/types/novamente';
import type { OrdenacaoAlunos } from '@/features/alunos/useAlunos';

const ROTULOS_ORDENACAO: Record<OrdenacaoAlunos, string> = {
  'nome:asc': M.alunos.ordenarNomeAsc,
  'nome:desc': M.alunos.ordenarNomeDesc,
  'criado_em:desc': M.alunos.ordenarRecentes,
};

export function AlunosSkeleton() {
  return (
    <div className="space-y-3" aria-busy="true" aria-label={M.comum.carregando}>
      {Array.from({ length: 6 }).map((_, i) => (
        <Skeleton key={i} className="h-16 w-full" />
      ))}
    </div>
  );
}

export function AlunosView() {
  const { data, isLoading, error, refetch, filtros, busca, setBusca, atualizar } = useAlunos();
  const criarAluno = useCriarAluno();
  const atualizarAluno = useAtualizarAluno();
  const excluirAluno = useExcluirAluno();
  const campoBusca = useRef<HTMLInputElement>(null);
  const [formAberto, setFormAberto] = useState(false);
  const [editando, setEditando] = useState<AlunoResumo | null>(null);
  const [excluindo, setExcluindo] = useState<AlunoResumo | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);

  const temFiltros = Boolean(filtros.q || filtros.status);

  // O input é não-controlado para preservar o cursor e o foco enquanto o
  // debounce não confirma a busca na URL.
  useEffect(() => {
    const campo = campoBusca.current;
    if (campo && campo.value !== busca) campo.value = busca;
  }, [busca]);

  const abrirCriacao = () => {
    setEditando(null);
    setFormAberto(true);
  };

  const abrirEdicao = (aluno: AlunoResumo) => {
    setEditando(aluno);
    setFormAberto(true);
  };

  const salvar = async (dados: AlunoCriacao) => {
    if (editando) {
      await atualizarAluno.mutateAsync({ alunoId: editando.aluno_id, dados });
      setAviso(M.alunos.toastEditado);
      return;
    }
    await criarAluno.mutateAsync(dados);
    setAviso(M.alunos.toastCriado);
  };

  const excluir = async () => {
    if (!excluindo) return;
    await excluirAluno.mutateAsync(excluindo.aluno_id);
    setAviso(M.alunos.toastExcluido);
    setExcluindo(null);
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold">{M.alunos.titulo}</h1>
        <Button onClick={abrirCriacao}>{M.alunos.novo}</Button>
      </div>

      <div className="flex flex-wrap gap-3">
        <label className="sr-only" htmlFor="alunos-busca">
          {M.alunos.busca}
        </label>
        <input
          ref={campoBusca}
          id="alunos-busca"
          type="search"
          defaultValue={busca}
          placeholder={M.alunos.buscaPlaceholder}
          onChange={(evento) => setBusca(evento.target.value)}
          className="h-10 min-w-[240px] flex-1 rounded-md border bg-[var(--surface)] px-3 text-sm"
        />

        <label className="sr-only" htmlFor="alunos-status">
          {M.alunos.todosStatus}
        </label>
        <select
          id="alunos-status"
          value={filtros.status ?? ''}
          onChange={(evento) =>
            atualizar({
              status: (evento.target.value || undefined) as StatusAluno | undefined,
              pagina: 1,
            })
          }
          className="h-10 rounded-md border bg-[var(--surface)] px-3 text-sm"
        >
          <option value="">{M.alunos.todosStatus}</option>
          <option value="ativo">{M.alunos.statusAtivo}</option>
          <option value="inativo">{M.alunos.statusInativo}</option>
        </select>

        <label className="sr-only" htmlFor="alunos-ordenar">
          {M.alunos.ordenar}
        </label>
        <select
          id="alunos-ordenar"
          value={filtros.ordenar}
          onChange={(evento) =>
            atualizar({ ordenar: evento.target.value as OrdenacaoAlunos, pagina: 1 })
          }
          className="h-10 rounded-md border bg-[var(--surface)] px-3 text-sm"
        >
          {ORDENACOES_ALUNOS.map((ordenacao) => (
            <option key={ordenacao} value={ordenacao}>
              {ROTULOS_ORDENACAO[ordenacao]}
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
          <p>{aviso}</p>
        </div>
      )}

      {isLoading && <AlunosSkeleton />}

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

      {data && data.itens.length === 0 && !error && temFiltros && (
        <div className="rounded-xl border border-dashed p-10 text-center">
          <p className="text-[var(--fg-muted)]">{M.alunos.vazioFiltros}</p>
          <Button
            variant="outline"
            className="mt-4"
            onClick={() => atualizar({ q: '', status: undefined, pagina: 1 })}
          >
            {M.alunos.limparFiltros}
          </Button>
        </div>
      )}

      {data && data.itens.length === 0 && !error && !temFiltros && (
        <div className="rounded-xl border border-dashed p-10 text-center">
          <p className="text-[var(--fg-muted)]">{M.alunos.vazio}</p>
          <Button className="mt-4" onClick={abrirCriacao}>
            {M.alunos.vazioCta}
          </Button>
        </div>
      )}

      {data && data.itens.length > 0 && (
        <div className="overflow-x-auto" data-tour="empresa-alunos-lista">
          <table className="block w-full md:table">
            <caption className="sr-only">{M.alunos.titulo}</caption>
            <thead className="hidden md:table-header-group">
              <tr className="border-b text-left text-xs uppercase tracking-wide text-[var(--fg-muted)]">
                <th scope="col" className="px-3 py-2">
                  {M.alunos.colunaNome}
                </th>
                <th scope="col" className="px-3 py-2">
                  {M.alunos.colunaEmail}
                </th>
                <th scope="col" className="px-3 py-2">
                  {M.alunos.colunaStatus}
                </th>
                <th scope="col" className="px-3 py-2">
                  {M.alunos.colunaMateriais}
                </th>
                <th scope="col" className="px-3 py-2">
                  {M.alunos.colunaCriado}
                </th>
                <th scope="col" className="px-3 py-2 text-right">
                  {M.alunos.colunaAcoes}
                </th>
              </tr>
            </thead>
            <tbody className="block md:table-row-group">
              {data.itens.map((aluno) => (
                <AlunoCard
                  key={aluno.aluno_id}
                  aluno={aluno}
                  onEditar={abrirEdicao}
                  onExcluir={setExcluindo}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}

      {data && data.total > 0 && (
        <nav aria-label={M.alunos.paginacao} className="flex items-center justify-center gap-3">
          <Button
            variant="outline"
            disabled={data.pagina <= 1}
            onClick={() => atualizar({ pagina: data.pagina - 1 })}
          >
            {M.alunos.anterior}
          </Button>
          <span className="text-sm text-[var(--fg-muted)]">
            {M.alunos.pagina(data.pagina, data.total_paginas)}
          </span>
          <Button
            variant="outline"
            disabled={data.pagina >= data.total_paginas}
            onClick={() => atualizar({ pagina: data.pagina + 1 })}
          >
            {M.alunos.proxima}
          </Button>
        </nav>
      )}

      {formAberto && (
        <AlunoFormDialog
          key={editando?.aluno_id ?? 'novo'}
          aluno={editando}
          open
          onOpenChange={(aberto) => {
            if (!aberto) {
              setFormAberto(false);
              setEditando(null);
            }
          }}
          salvar={salvar}
        />
      )}

      {excluindo && (
        <AlunoDeleteDialog
          aluno={excluindo}
          open
          onOpenChange={(aberto) => {
            if (!aberto) setExcluindo(null);
          }}
          excluir={excluir}
        />
      )}
    </div>
  );
}
