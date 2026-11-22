'use client';

import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { AlertTriangle } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { AlunoDeleteDialog } from './AlunoDeleteDialog';
import { AlunoFormDialog } from './AlunoFormDialog';
import { VinculosPanel } from './VinculosPanel';
import { useAluno, useAtualizarAluno, useExcluirAluno } from '@/features/alunos/useAlunos';
import { ErroApi, mensagemDoErro } from '@/services/api/erros';
import { M } from '@/lib/mensagens';
import { ROTAS } from '@/lib/rotas';
import type { AlunoCriacao } from '@/types/novamente';

export interface AlunoDetalheViewProps {
  alunoId: string;
}

export function AlunoDetalheSkeleton() {
  return (
    <div className="space-y-4" aria-busy="true" aria-label={M.alunos.detalheCarregando}>
      <Skeleton className="h-5 w-40" />
      <Skeleton className="h-9 w-72" />
      <Skeleton className="h-24 w-full" />
    </div>
  );
}

export function AlunoDetalheView({ alunoId }: AlunoDetalheViewProps) {
  const router = useRouter();
  const params = useSearchParams();
  const { data: aluno, isLoading, error, refetch } = useAluno(alunoId);
  const atualizarAluno = useAtualizarAluno();
  const excluirAluno = useExcluirAluno();

  const [editando, setEditando] = useState(false);
  const [excluindo, setExcluindo] = useState(false);
  const [pendentes, setPendentes] = useState(false);
  const [aviso, setAviso] = useState<string | null>(null);
  const ignorarProximoPopState = useRef(false);

  const query = params.toString();
  const voltarHref = query ? `${ROTAS.empresaAlunos}?${query}` : ROTAS.empresaAlunos;

  // Guarda central de navegação: cobre qualquer link same-origin (logo, nav,
  // "Área do aluno", voltar) e o botão Voltar do navegador, não só o link
  // interno. `beforeunload` continua no painel como segunda camada.
  useEffect(() => {
    if (!pendentes) return;
    ignorarProximoPopState.current = false;

    const aoClicar = (evento: MouseEvent) => {
      if (evento.defaultPrevented || evento.button !== 0) return;
      if (evento.metaKey || evento.ctrlKey || evento.shiftKey || evento.altKey) return;

      const alvo = evento.target;
      if (!(alvo instanceof Element)) return;
      const link = alvo.closest('a');
      if (!(link instanceof HTMLAnchorElement)) return;
      if (link.target && link.target !== '_self') return;
      if (link.hasAttribute('download')) return;

      const href = link.getAttribute('href');
      if (!href || href.startsWith('#') || href.startsWith('mailto:') || href.startsWith('tel:')) {
        return;
      }

      let destino: URL;
      try {
        destino = new URL(link.href, window.location.href);
      } catch {
        return;
      }
      if (destino.origin !== window.location.origin) return;

      if (!window.confirm(M.alunos.vinculosAoSair)) evento.preventDefault();
    };

    const aoVoltarNoNavegador = () => {
      if (ignorarProximoPopState.current) {
        ignorarProximoPopState.current = false;
        return;
      }
      if (window.confirm(M.alunos.vinculosAoSair)) return;
      // O popstate já mudou a URL; volta para a entrada de detalhe. O próximo
      // popstate é o nosso próprio forward e não deve pedir confirmação de novo.
      ignorarProximoPopState.current = true;
      window.history.forward();
    };

    document.addEventListener('click', aoClicar, true);
    window.addEventListener('popstate', aoVoltarNoNavegador);
    return () => {
      document.removeEventListener('click', aoClicar, true);
      window.removeEventListener('popstate', aoVoltarNoNavegador);
    };
  }, [pendentes]);

  const voltar = (
    <Link
      href={voltarHref}
      className="text-sm text-[var(--fg-muted)] underline-offset-4 hover:underline"
    >
      {M.alunos.voltarLista}
    </Link>
  );

  if (isLoading) return <AlunoDetalheSkeleton />;

  if (error instanceof ErroApi && error.status === 404) {
    return (
      <div className="space-y-4">
        {voltar}
        <div role="alert" className="rounded-xl border p-6">
          <p className="font-medium">{M.alunos.naoEncontrado}</p>
          <p className="mt-1 text-sm text-[var(--fg-muted)]">{M.alunos.naoEncontradoDetalhe}</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-4">
        {voltar}
        <div role="alert" className="rounded-xl border border-[var(--danger)] p-6">
          <p className="flex items-center gap-2 text-[var(--danger)]">
            <AlertTriangle aria-hidden className="h-5 w-5" />
            {mensagemDoErro(error)}
          </p>
          <Button className="mt-4" onClick={() => refetch()}>
            {M.comum.tentarNovamente}
          </Button>
        </div>
      </div>
    );
  }

  if (!aluno) return <AlunoDetalheSkeleton />;

  const ativo = aluno.status === 'ativo';

  const salvarEdicao = async (dados: AlunoCriacao) => {
    await atualizarAluno.mutateAsync({ alunoId: aluno.aluno_id, dados });
    setAviso(M.alunos.toastEditado);
    setEditando(false);
  };

  const excluir = async () => {
    await excluirAluno.mutateAsync(aluno.aluno_id);
    setExcluindo(false);
    router.push(voltarHref);
  };

  return (
    <div className="space-y-6">
      {voltar}

      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-1">
          <h1 className="text-2xl font-semibold">{aluno.nome}</h1>
          <p className="break-all text-sm text-[var(--fg-muted)]">{aluno.email}</p>
          <div className="flex flex-wrap items-center gap-2 pt-1 text-sm">
            <Badge variant={ativo ? 'secondary' : 'outline'}>
              {ativo ? M.alunos.statusAtivo : M.alunos.statusInativo}
            </Badge>
            <span className="text-[var(--fg-muted)]">
              {M.alunos.totalMateriais(aluno.total_materiais)}
            </span>
          </div>
        </div>

        <div className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={() => setEditando(true)}>
            {M.alunos.editar}
          </Button>
          <Button variant="destructive" onClick={() => setExcluindo(true)}>
            {M.alunos.excluir}
          </Button>
        </div>
      </header>

      {aviso && (
        <div
          role="status"
          aria-live="polite"
          className="rounded-lg border border-[var(--accent)] px-4 py-3 text-sm"
        >
          {aviso}
        </div>
      )}

      <VinculosPanel alunoId={aluno.aluno_id} onAlteracoesPendentes={setPendentes} />

      {editando && (
        <AlunoFormDialog
          key={aluno.aluno_id}
          aluno={aluno}
          open
          onOpenChange={(aberto) => {
            if (!aberto) setEditando(false);
          }}
          salvar={salvarEdicao}
        />
      )}

      {excluindo && (
        <AlunoDeleteDialog
          aluno={aluno}
          open
          onOpenChange={(aberto) => {
            if (!aberto) setExcluindo(false);
          }}
          excluir={excluir}
        />
      )}
    </div>
  );
}
