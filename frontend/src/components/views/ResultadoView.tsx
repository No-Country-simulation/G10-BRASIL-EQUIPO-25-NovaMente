'use client';

import { AlertTriangle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { ContentRenderer } from './ContentRenderer';
import { OCIPanel } from './OCIPanel';
import { ResultadoHeader } from './ResultadoHeader';
import { useAdaptation } from '@/features/adaptations/useAdaptation';
import { useOciStatus } from '@/features/oci/useOciStatus';
import { M } from '@/lib/mensagens';
import { ErroApi, mensagemDoErro } from '@/services/api/erros';

export function ResultadoView({ adaptacaoId }: { adaptacaoId: string }) {
  const { data: pacote, isLoading, error, refetch } = useAdaptation(adaptacaoId);
  const { data: oci } = useOciStatus();

  if (isLoading) {
    return (
      <div className="grid gap-6 lg:grid-cols-[1fr_340px]" aria-busy="true" aria-label={M.comum.carregando}>
        <div className="space-y-4">
          <Skeleton className="h-8 w-2/3" />
          <Skeleton className="h-[360px] w-full" />
        </div>
        <Skeleton className="h-[420px] w-full" />
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
      <ResultadoHeader pacote={pacote} />
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
