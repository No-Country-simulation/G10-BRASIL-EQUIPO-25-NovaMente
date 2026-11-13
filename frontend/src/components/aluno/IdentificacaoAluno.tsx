'use client';

import { useMemo, useState } from 'react';
import Link from 'next/link';
import { AlertTriangle, Search } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import {
  useIdentificacaoAluno,
  type IdentidadeAluno,
} from '@/features/aluno/useIdentidadeAluno';
import { mensagemDoErro } from '@/services/api/erros';
import { M } from '@/lib/mensagens';
import { ROTAS } from '@/lib/rotas';
import type { IdentificacaoAlunoItem } from '@/types/novamente';

export interface IdentificacaoAlunoProps {
  onIdentificar: (aluno: IdentidadeAluno) => void;
  aviso?: string | null;
}

export function IdentificacaoSkeleton() {
  return (
    <div className="space-y-2" aria-busy="true" aria-label={M.comum.carregando}>
      {Array.from({ length: 4 }).map((_, indice) => (
        <Skeleton key={indice} className="h-12 w-full" />
      ))}
    </div>
  );
}

export function IdentificacaoAluno({ onIdentificar, aviso }: IdentificacaoAlunoProps) {
  const consulta = useIdentificacaoAluno();
  const [busca, setBusca] = useState('');
  const [selecionado, setSelecionado] = useState<IdentificacaoAlunoItem | null>(null);

  const alunos = useMemo(() => {
    const termo = busca.trim().toLowerCase();
    const todos = consulta.data ?? [];
    if (!termo) return todos;
    return todos.filter((aluno) => aluno.nome.toLowerCase().includes(termo));
  }, [busca, consulta.data]);

  const semAlunos = !consulta.isLoading && !consulta.error && consulta.data?.length === 0;
  const semResultados =
    !consulta.isLoading && !consulta.error && (consulta.data?.length ?? 0) > 0 && alunos.length === 0;

  return (
    <section data-tour="aluno-identificacao" className="mx-auto max-w-2xl space-y-6">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold">{M.aluno.identificacao.titulo}</h1>
        <p className="text-sm text-[var(--fg-muted)]">{M.aluno.identificacao.descricao}</p>
      </header>

      {aviso && (
        <p
          role="alert"
          className="rounded-lg border border-[var(--danger)] px-4 py-3 text-sm text-[var(--danger)]"
        >
          {aviso}
        </p>
      )}

      <p className="text-xs text-[var(--fg-muted)]">{M.aluno.identificacao.avisoSemSenha}</p>

      <div className="relative">
        <label htmlFor="aluno-busca" className="sr-only">
          {M.aluno.identificacao.busca}
        </label>
        <Search
          aria-hidden
          className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--fg-muted)]"
        />
        <input
          id="aluno-busca"
          type="search"
          value={busca}
          onChange={(evento) => setBusca(evento.target.value)}
          placeholder={M.aluno.identificacao.buscaPlaceholder}
          className="h-10 w-full rounded-md border bg-[var(--surface)] pl-9 pr-3 text-sm"
        />
      </div>

      {consulta.isLoading && <IdentificacaoSkeleton />}

      {consulta.error && (
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

      {semAlunos && (
        <div className="rounded-xl border border-dashed p-10 text-center">
          <p className="text-[var(--fg-muted)]">{M.aluno.identificacao.vazio}</p>
          <Button asChild className="mt-4">
            <Link href={ROTAS.empresaAlunos}>{M.aluno.identificacao.vazioCta}</Link>
          </Button>
        </div>
      )}

      {semResultados && (
        <div className="rounded-xl border border-dashed p-8 text-center">
          <p className="text-[var(--fg-muted)]">{M.aluno.identificacao.semResultados}</p>
          <Button variant="outline" className="mt-4" onClick={() => setBusca('')}>
            {M.aluno.identificacao.limparBusca}
          </Button>
        </div>
      )}

      {alunos.length > 0 && (
        <ul className="space-y-2" aria-label={M.aluno.identificacao.lista}>
          {alunos.map((aluno) => {
            const ativo = selecionado?.aluno_id === aluno.aluno_id;
            return (
              <li key={aluno.aluno_id}>
                <button
                  type="button"
                  aria-pressed={ativo}
                  aria-label={M.aluno.identificacao.selecionar(aluno.nome)}
                  onClick={() => setSelecionado(aluno)}
                  className={
                    ativo
                      ? 'flex min-h-11 w-full items-center rounded-lg border border-[var(--accent)] bg-[var(--accent-muted)] px-4 py-2 text-left text-sm font-medium'
                      : 'flex min-h-11 w-full items-center rounded-lg border px-4 py-2 text-left text-sm hover:border-[var(--accent)]'
                  }
                >
                  {aluno.nome}
                </button>
              </li>
            );
          })}
        </ul>
      )}

      <div className="flex justify-end">
        <Button
          disabled={!selecionado}
          onClick={() => {
            if (selecionado) onIdentificar(selecionado);
          }}
        >
          {M.aluno.identificacao.entrar}
        </Button>
      </div>
    </section>
  );
}
