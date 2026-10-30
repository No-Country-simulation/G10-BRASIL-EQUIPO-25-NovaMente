import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { describe, expect, it, vi } from 'vitest';
import { useAdaptationJob } from './useAdaptationJob';
import { ApiProvider } from '@/services/api/ApiProvider';
import { ErroApi } from '@/services/api/erros';
import type { NovaMenteApi } from '@/services/api/NovaMenteApi';
import type { AdaptacaoPacote, JobResposta } from '@/types/novamente';

const pacote = { adaptacao_id: 'a1' } as unknown as AdaptacaoPacote;

const emAndamento = (progresso: number): JobResposta => ({
  job_id: 'j1',
  status: 'running',
  etapa_atual: 'extraindo',
  etapas_concluidas: [],
  progresso_percentual: progresso,
  iniciado_em: '2026-10-21T14:02:11Z',
  atualizado_em: '2026-10-21T14:02:12Z',
});

function montar(obterJob: NovaMenteApi['obterJob']) {
  const api = { obterJob } as unknown as NovaMenteApi;
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const wrapper = ({ children }: { children: ReactNode }) => (
    <ApiProvider client={api}>
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    </ApiProvider>
  );
  return { wrapper, client };
}

describe('useAdaptationJob', () => {
  it('polla e chama aoConcluir com o pacote', async () => {
    const respostas = [
      emAndamento(20),
      emAndamento(60),
      { ...emAndamento(100), status: 'succeeded' as const, etapa_atual: null, adaptacao_id: 'a1', resultado: pacote },
    ];
    const obterJob = vi.fn().mockImplementation(() => Promise.resolve(respostas.shift()!));
    const aoConcluir = vi.fn();
    const { wrapper } = montar(obterJob);

    renderHook(() => useAdaptationJob('j1', aoConcluir, { intervaloRapidoMs: 10 }), { wrapper });

    await waitFor(() => expect(aoConcluir).toHaveBeenCalledWith(pacote), { timeout: 3000 });
    expect(obterJob.mock.calls.length).toBeGreaterThanOrEqual(3);
  });

  it('marca estourou após o timeout e para de pollar', async () => {
    const obterJob = vi.fn().mockResolvedValue(emAndamento(10));
    const { wrapper } = montar(obterJob);

    const { result } = renderHook(
      () => useAdaptationJob('j1', vi.fn(), { intervaloRapidoMs: 10, timeoutMs: 40 }),
      { wrapper },
    );

    await waitFor(() => expect(result.current.estourou).toBe(true), { timeout: 3000 });
    const chamadas = obterJob.mock.calls.length;
    await new Promise((r) => setTimeout(r, 80));
    expect(obterJob.mock.calls.length).toBe(chamadas);
  });

  it('sinaliza job perdido quando a API responde 404', async () => {
    const obterJob = vi.fn().mockRejectedValue(
      new ErroApi({ erro: { codigo: 'JOB_NAO_ENCONTRADO', mensagem: 'sumiu' } }, 404),
    );
    const { wrapper } = montar(obterJob);

    const { result } = renderHook(() => useAdaptationJob('j1', vi.fn(), { intervaloRapidoMs: 10 }), { wrapper });

    await waitFor(() => expect(result.current.perdido).toBe(true), { timeout: 3000 });
  });

  it('não estoura depois de o job terminar', async () => {
    const obterJob = vi.fn().mockResolvedValue({
      ...emAndamento(30),
      status: 'failed' as const,
      etapa_atual: null,
      erro: { codigo: 'DOCUMENTO_ILEGIVEL' as const, mensagem: 'PDF sem texto.' },
    });
    const { wrapper } = montar(obterJob);

    const { result } = renderHook(
      () => useAdaptationJob('j1', vi.fn(), { intervaloRapidoMs: 10, timeoutMs: 60 }),
      { wrapper },
    );

    await waitFor(() => expect(result.current.job?.status).toBe('failed'), { timeout: 3000 });
    await new Promise((r) => setTimeout(r, 150));
    expect(result.current.estourou).toBe(false);
  });
});
