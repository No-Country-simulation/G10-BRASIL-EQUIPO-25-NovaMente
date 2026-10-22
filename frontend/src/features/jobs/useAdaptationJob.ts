'use client';

import { useQuery } from '@tanstack/react-query';
import { useEffect, useRef, useState } from 'react';
import { useApi } from '@/services/api/ApiProvider';
import { ErroApi } from '@/services/api/erros';
import {
  INTERVALO_POLL_LONGO_MS,
  INTERVALO_POLL_MS,
  JANELA_POLL_RAPIDO_MS,
  LIMITE_TEMPO_JOB_MS,
} from '@/lib/constants';
import type { AdaptacaoPacote, JobResposta } from '@/types/novamente';

interface Opcoes {
  intervaloRapidoMs?: number;
  intervaloLongoMs?: number;
  janelaRapidaMs?: number;
  timeoutMs?: number;
}

const STATUS_TERMINAIS: JobResposta['status'][] = ['succeeded', 'failed', 'cancelled'];

export function useAdaptationJob(
  jobId: string | null,
  aoConcluir: (pacote: AdaptacaoPacote) => void,
  opcoes: Opcoes = {},
) {
  const api = useApi();
  const {
    intervaloRapidoMs = INTERVALO_POLL_MS,
    intervaloLongoMs = INTERVALO_POLL_LONGO_MS,
    janelaRapidaMs = JANELA_POLL_RAPIDO_MS,
    timeoutMs = LIMITE_TEMPO_JOB_MS,
  } = opcoes;

  const inicioRef = useRef(0);
  const aoConcluirRef = useRef(aoConcluir);
  const concluidoRef = useRef<string | null>(null);
  const [estouro, setEstouro] = useState<{ jobId: string | null; estourou: boolean }>({
    jobId: null,
    estourou: false,
  });

  useEffect(() => {
    aoConcluirRef.current = aoConcluir;
  }, [aoConcluir]);

  useEffect(() => {
    concluidoRef.current = null;
    inicioRef.current = jobId ? Date.now() : 0;
    if (!jobId) return;
    const timer = setTimeout(() => setEstouro({ jobId, estourou: true }), timeoutMs);
    return () => clearTimeout(timer);
  }, [jobId, timeoutMs]);

  const estourou = Boolean(jobId) && estouro.jobId === jobId && estouro.estourou;

  const consulta = useQuery({
    queryKey: ['job', jobId],
    queryFn: () => api.obterJob(jobId as string),
    enabled: Boolean(jobId) && !estourou,
    refetchInterval: (consultaAtual) => {
      const status = consultaAtual.state.data?.status;
      if (status && STATUS_TERMINAIS.includes(status)) return false;
      // Job inexistente não volta: seguir pollando só repetiria o 404 para sempre.
      if (consultaAtual.state.error instanceof ErroApi && consultaAtual.state.error.status === 404) return false;
      // A primeira avaliação acontece antes do efeito que registra `inicioRef`;
      // nesse caso o job acabou de começar e o intervalo é o rápido.
      if (!inicioRef.current) return intervaloRapidoMs;
      return Date.now() - inicioRef.current < janelaRapidaMs ? intervaloRapidoMs : intervaloLongoMs;
    },
    refetchIntervalInBackground: false,
  });

  const job = consulta.data;

  useEffect(() => {
    if (job?.status !== 'succeeded' || !job.resultado) return;
    if (concluidoRef.current === job.resultado.adaptacao_id) return;
    concluidoRef.current = job.resultado.adaptacao_id;
    aoConcluirRef.current(job.resultado);
  }, [job]);

  const perdido =
    consulta.error instanceof ErroApi && consulta.error.problema.erro.codigo === 'JOB_NAO_ENCONTRADO';

  return {
    job,
    erro: consulta.error,
    carregando: consulta.isLoading,
    estourou,
    perdido,
    cancelado: job?.status === 'cancelled',
  };
}
