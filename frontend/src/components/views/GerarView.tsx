'use client';

import { useRouter } from 'next/navigation';
import { useCallback, useState } from 'react';
import { IngestionForm } from '@/components/forms/IngestionForm';
import { JobProgress } from './JobProgress';
import { Button } from '@/components/ui/button';
import { useApi } from '@/services/api/ApiProvider';
import { mensagemDoErro } from '@/services/api/erros';
import { useAdaptationJob } from '@/features/jobs/useAdaptationJob';
import { M } from '@/lib/mensagens';
import type { JobResposta } from '@/types/novamente';

export function GerarView() {
  const router = useRouter();
  const api = useApi();
  const [jobId, setJobId] = useState<string | null>(null);
  const [repetir, setRepetir] = useState<(() => Promise<JobResposta | null>) | null>(null);
  const [erroAcao, setErroAcao] = useState<string | null>(null);

  const aoConcluir = useCallback(
    (pacote: { adaptacao_id: string }) => router.push(`/resultado/${pacote.adaptacao_id}`),
    [router],
  );

  const { job, estourou, perdido, erro } = useAdaptationJob(jobId, aoConcluir);
  // Só trava o formulário enquanto a geração está de fato em andamento: numa
  // falha o usuário precisa poder corrigir o documento e enviar de novo.
  const falhou = estourou || perdido || job?.status === 'failed';

  const aoCriar = useCallback((novo: JobResposta, repetirEnvio: () => Promise<JobResposta | null>) => {
    setErroAcao(null);
    setRepetir(() => repetirEnvio);
    setJobId(novo.job_id);
  }, []);

  const cancelar = useCallback(async () => {
    if (!jobId) return;
    try {
      await api.cancelarJob(jobId);
    } catch {
      // Mesmo se o cancelamento falhar, o usuário volta ao formulário.
    } finally {
      setJobId(null);
    }
  }, [api, jobId]);

  const tentarNovamente = useCallback(async () => {
    setErroAcao(null);
    setJobId(null);
    try {
      const novo = await repetir?.();
      if (novo) setJobId(novo.job_id);
    } catch (falha) {
      setErroAcao(mensagemDoErro(falha));
    }
  }, [repetir]);

  return (
    <div className="grid gap-8 lg:grid-cols-[380px_1fr]">
      <section aria-labelledby="form-titulo">
        <h1 id="form-titulo" className="mb-4 text-xl font-semibold">
          {M.formulario.titulo}
        </h1>
        <IngestionForm onCriado={aoCriar} desabilitado={Boolean(jobId) && !falhou} />
      </section>

      <section aria-label={M.job.regiaoResultado}>
        {erroAcao && (
          <div role="alert" className="mb-4 rounded-md border border-[var(--danger)] p-3 text-sm text-[var(--danger)]">
            {erroAcao}
          </div>
        )}

        {jobId && job ? (
          <JobProgress
            job={job}
            estourou={estourou}
            perdido={perdido}
            aoCancelar={cancelar}
            aoTentarNovamente={tentarNovamente}
          />
        ) : jobId && (perdido || erro || estourou) ? (
          <div role="alert" className="rounded-xl border border-[var(--danger)] p-6">
            <p className="text-[var(--danger)]">
              {perdido ? M.job.perdida : erro ? mensagemDoErro(erro) : M.job.timeout}
            </p>
            <Button className="mt-4" onClick={tentarNovamente}>
              {M.comum.tentarNovamente}
            </Button>
          </div>
        ) : jobId ? (
          <div className="h-[320px] animate-pulse rounded-xl border bg-[var(--surface)]" aria-label={M.comum.carregando} />
        ) : (
          <div className="flex h-[320px] items-center justify-center rounded-xl border border-dashed text-sm text-[var(--fg-muted)]">
            {M.job.aguardando}
          </div>
        )}
      </section>
    </div>
  );
}
