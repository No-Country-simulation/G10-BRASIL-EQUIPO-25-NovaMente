'use client';

import { AlertTriangle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { ContentRenderer } from './ContentRenderer';
import { OCIPanel } from './OCIPanel';
import { ResultadoHeader } from './ResultadoHeader';
import { useAdaptation } from '@/features/adaptations/useAdaptation';
import { useExport } from '@/features/adaptations/useExport';
import { useOciStatus } from '@/features/oci/useOciStatus';
import { M } from '@/lib/mensagens';
import { ErroApi, mensagemDoErro } from '@/services/api/erros';

export function ResultadoView({ adaptacaoId }: { adaptacaoId: string }) {
  const { data: pacote, isPending, error, refetch } = useAdaptation(adaptacaoId);
  const { data: oci } = useOciStatus();
  // Uma única instância para header e menu; o hook aceita null para poder ser
  // chamado antes dos early returns sem quebrar a ordem dos hooks.
  const exportacao = useExport(pacote ?? null);

  if (isPending) {
    // Espelha tags, classes e alturas do conteúdo final para o React reutilizar
    // os mesmos nós: header de 92 px no desktop (288 px em 390 px, quando o
    // título quebra e as ações empilham), introdução de duas linhas e grid.
    return (
      <div role="status">
        <span className="sr-only">{M.comum.carregando}</span>
        <header className="mb-8 space-y-4">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="min-w-0">
              <Skeleton className="h-8 w-2/3" />
              <Skeleton className="mt-1 h-5 w-1/3" />
            </div>
            {/* Exportar / JSON / Nova geração: no mobile os três botões quebram
                em duas linhas (72 px); daí para cima cabem em uma (32 px). */}
            <div className="flex flex-col items-end gap-2">
              <div className="flex flex-wrap items-center justify-end gap-2">
                <Skeleton className="h-8 w-40" />
                <Skeleton className="h-8 w-36" />
                <Skeleton className="h-8 w-32" />
              </div>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Skeleton className="h-5 w-24" />
            <Skeleton className="h-5 w-20" />
            <Skeleton className="h-5 w-16" />
            <Skeleton className="h-5 w-24" />
          </div>
        </header>
        <div className="grid gap-8 lg:grid-cols-[1fr_340px]">
          <div className="min-w-0">
            {/* O parágrafo real tem 48 px (duas linhas de 24 px). */}
            <Skeleton className="mb-6 min-h-12 w-full" />
            <Skeleton className="h-[440px] w-full" />
          </div>
          <Skeleton className="h-[420px] w-full" />
        </div>
      </div>
    );
  }

  if (error) {
    const naoEncontrado = error instanceof ErroApi && error.status === 404;
    return (
      <div role="alert" className="rounded-xl border border-[var(--danger)] p-6">
        <h2 className="flex items-center gap-2 font-semibold text-[var(--danger)]">
          <AlertTriangle aria-hidden className="h-5 w-5" />
          {naoEncontrado ? M.resultado.naoEncontrado : mensagemDoErro(error)}
        </h2>
        <div className="mt-4 flex gap-3">
          {!naoEncontrado && <Button onClick={() => refetch()}>{M.comum.tentarNovamente}</Button>}
          <Button asChild variant="outline">
            <a href="/historico">{M.resultado.irParaHistorico}</a>
          </Button>
        </div>
      </div>
    );
  }

  if (!pacote) return null;

  return (
    <div>
      <ResultadoHeader pacote={pacote} exportacao={exportacao} />
      <div className="grid gap-8 lg:grid-cols-[1fr_340px]">
        <div className="min-w-0">
          <p className="mb-6 text-[var(--fg-muted)]">{pacote.conteudo_adaptado.introducao_contextualizada}</p>
          <ContentRenderer conteudo={pacote.conteudo_adaptado} />
        </div>
        <OCIPanel armazenamento={pacote.armazenamento_oci} avaliacao={pacote.avaliacao_qualidade} oci={oci} />
      </div>
    </div>
  );
}
