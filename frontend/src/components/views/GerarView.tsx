'use client';

import { useRouter } from 'next/navigation';
import { useCallback, useEffect, useRef, useState } from 'react';
import { IngestionForm } from '@/components/forms/IngestionForm';
import { JobProgress } from './JobProgress';
import { Button } from '@/components/ui/button';
import { useApi } from '@/services/api/ApiProvider';
import { mensagemComEspera, mensagemDoErro } from '@/services/api/erros';
import { useAdaptationJob } from '@/features/jobs/useAdaptationJob';
import { M } from '@/lib/mensagens';
import { ROTAS } from '@/lib/rotas';
import type { JobResposta } from '@/types/novamente';

export function GerarView() {
  const router = useRouter();
  const api = useApi();
  const [jobId, setJobId] = useState<string | null>(null);
  const [repetir, setRepetir] = useState<(() => Promise<JobResposta | null>) | null>(null);
  const [erroAcao, setErroAcao] = useState<string | null>(null);

  const aoConcluir = useCallback(
    (pacote: { adaptacao_id: string }) => router.push(ROTAS.empresaResultado(pacote.adaptacao_id)),
    [router],
  );

  const { job, estourou, perdido, erro } = useAdaptationJob(jobId, aoConcluir);
  // Só trava o formulário enquanto a geração está de fato em andamento: numa
  // falha o usuário precisa poder corrigir o documento e enviar de novo.
  const falhou = Boolean(erro) || estourou || perdido || job?.status === 'failed';

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
      setErroAcao(mensagemComEspera(falha));
    }
  }, [repetir]);

  // Abaixo de xl o resultado fica embaixo do formulário: ao iniciar a geração,
  // leva a tela até o progresso para a pessoa não precisar procurar.
  const resultadoRef = useRef<HTMLElement>(null);
  useEffect(() => {
    if (!jobId || typeof window === 'undefined') return;
    if (window.matchMedia?.('(min-width: 1280px)').matches) return;
    const reduzido = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
    resultadoRef.current?.scrollIntoView?.({ behavior: reduzido ? 'auto' : 'smooth', block: 'start' });
  }, [jobId]);

  return (
    // Em telas largas ocupa a altura útil da janela: documento, parâmetros e
    // progresso lado a lado, sem rolagem da página.
    <div className="grid grid-cols-1 gap-6 xl:h-[calc(100dvh-13.5rem)] xl:max-h-[960px] xl:min-h-[560px] xl:grid-cols-[minmax(0,1fr)_380px]">
      <section
        aria-labelledby="form-titulo"
        data-tour="empresa-gerar-form"
        className="min-h-0 xl:flex xl:flex-col"
      >
        <IngestionForm
          onCriado={aoCriar}
          desabilitado={Boolean(jobId) && !falhou}
          titulo={
            <h1 id="form-titulo" className="text-xl font-semibold">
              {M.formulario.titulo}
            </h1>
          }
        />
      </section>

      <section
        ref={resultadoRef}
        aria-label={M.job.regiaoResultado}
        className="min-h-0 scroll-mt-20 xl:overflow-y-auto"
      >
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
          <div className="h-[320px] animate-pulse rounded-xl border bg-[var(--surface)] xl:h-full" aria-label={M.comum.carregando} />
        ) : (
          <div className="flex h-40 items-center justify-center rounded-xl border border-dashed p-6 text-center text-sm text-[var(--fg-muted)] xl:h-full">
            {M.job.aguardando}
          </div>
        )}
      </section>
    </div>
  );
}
