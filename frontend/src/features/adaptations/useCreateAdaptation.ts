'use client';

import { useCallback, useRef, useState } from 'react';
import { useApi } from '@/services/api/ApiProvider';
import type { AdaptacaoInput, AdaptacaoUploadInput, JobResposta } from '@/types/novamente';

export type Envio = AdaptacaoInput | AdaptacaoUploadInput;

export function useCreateAdaptation() {
  const api = useApi();
  const [enviando, setEnviando] = useState(false);
  const [job, setJob] = useState<JobResposta | null>(null);
  const ultimoEnvioRef = useRef<Envio | null>(null);

  const criar = useCallback(
    async (entrada: Envio) => {
      setEnviando(true);
      try {
        const resposta =
          'arquivo' in entrada ? await api.criarPorArquivo(entrada) : await api.criarPorTexto(entrada);
        ultimoEnvioRef.current = entrada;
        setJob(resposta);
        return resposta;
      } finally {
        setEnviando(false);
      }
    },
    [api],
  );

  const repetir = useCallback(async () => {
    const entrada = ultimoEnvioRef.current;
    if (!entrada) return null;
    return criar(entrada);
  }, [criar]);

  const cancelar = useCallback(async () => {
    if (!job) return;
    try {
      await api.cancelarJob(job.job_id);
    } finally {
      setJob(null);
    }
  }, [api, job]);

  return { criar, repetir, cancelar, enviando, job };
}
