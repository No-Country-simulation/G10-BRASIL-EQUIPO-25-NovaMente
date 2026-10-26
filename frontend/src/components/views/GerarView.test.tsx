import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { GerarView } from './GerarView';
import { ApiProvider } from '@/services/api/ApiProvider';
import type { NovaMenteApi } from '@/services/api/NovaMenteApi';
import type { AdaptacaoPacote, JobResposta } from '@/types/novamente';

const { push } = vi.hoisted(() => ({ push: vi.fn() }));
vi.mock('next/navigation', () => ({ useRouter: () => ({ push }) }));

const job = (over: Partial<JobResposta>): JobResposta => ({
  job_id: 'j1',
  status: 'queued',
  etapa_atual: null,
  etapas_concluidas: [],
  progresso_percentual: 0,
  iniciado_em: '2026-10-21T14:02:11Z',
  atualizado_em: '2026-10-21T14:02:11Z',
  ...over,
});

const falho = job({
  status: 'failed',
  erro: { codigo: 'DOCUMENTO_ILEGIVEL', mensagem: 'PDF sem texto.' },
});

const emAndamento = (id: string): JobResposta =>
  job({ job_id: id, status: 'running', etapa_atual: 'extraindo', progresso_percentual: 15 });

function montar({
  obterJob,
  criarPorTexto,
  cancelarJob = vi.fn(),
}: {
  obterJob: NovaMenteApi['obterJob'];
  criarPorTexto: NovaMenteApi['criarPorTexto'];
  cancelarJob?: NovaMenteApi['cancelarJob'];
}) {
  const api = {
    obterJob,
    criarPorTexto,
    criarPorArquivo: vi.fn(),
    cancelarJob,
  } as unknown as NovaMenteApi;
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <ApiProvider client={api}>
      <QueryClientProvider client={client}>
        <GerarView />
      </QueryClientProvider>
    </ApiProvider>,
  );
  return { api, client };
}

async function preencherEEnviar() {
  await userEvent.type(screen.getByLabelText(/título do documento/i), 'Introdução à VCN');
  fireEvent.change(screen.getByLabelText(/conteúdo técnico/i), { target: { value: 'a'.repeat(200) } });
  await userEvent.click(screen.getByRole('button', { name: /gerar material/i }));
}

describe('GerarView', () => {
  beforeEach(() => push.mockReset());

  it('reabilita o formulário quando o job falha', async () => {
    const criarPorTexto = vi.fn().mockResolvedValue(job({ job_id: 'j1' }));
    montar({ criarPorTexto, obterJob: vi.fn().mockResolvedValue(falho) });

    await preencherEEnviar();
    expect(await screen.findByText('PDF sem texto.')).toBeInTheDocument();

    const enviar = screen.getByRole('button', { name: /gerar material/i });
    expect(enviar).toBeEnabled();

    const titulo = screen.getByLabelText(/título do documento/i);
    expect(titulo).toBeEnabled();
    await userEvent.clear(titulo);
    await userEvent.type(titulo, 'Outro documento');
    expect(titulo).toHaveValue('Outro documento');
  });

  it('novo envio após falha substitui o job e volta ao progresso', async () => {
    const criarPorTexto = vi
      .fn()
      .mockResolvedValueOnce(job({ job_id: 'j1' }))
      .mockResolvedValueOnce(job({ job_id: 'j2' }));
    const obterJob = vi.fn().mockImplementation((id: string) => Promise.resolve(id === 'j2' ? emAndamento('j2') : falho));
    montar({ criarPorTexto, obterJob });

    await preencherEEnviar();
    expect(await screen.findByText('PDF sem texto.')).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: /gerar material/i }));

    await waitFor(() => expect(obterJob).toHaveBeenCalledWith('j2'));
    expect(criarPorTexto).toHaveBeenCalledTimes(2);
    expect(criarPorTexto.mock.calls[1][0]).toEqual(criarPorTexto.mock.calls[0][0]);
    await waitFor(() => expect(screen.queryByText('PDF sem texto.')).not.toBeInTheDocument());
    expect(screen.getByText('Gerando seu material')).toBeInTheDocument();
    expect(screen.getByText('Extraindo texto')).toBeInTheDocument();
    expect(push).not.toHaveBeenCalled();
  });

  it('navega uma única vez quando o job conclui', async () => {
    const pacote = { adaptacao_id: 'a1' } as unknown as AdaptacaoPacote;
    const concluido = job({
      status: 'succeeded',
      etapa_atual: null,
      etapas_concluidas: ['extraindo', 'chunking', 'embeddings', 'gerando', 'revisando', 'armazenando'],
      progresso_percentual: 100,
      adaptacao_id: 'a1',
      resultado: pacote,
    });
    const criarPorTexto = vi.fn().mockResolvedValue(job({ job_id: 'j1' }));
    montar({ criarPorTexto, obterJob: vi.fn().mockResolvedValue(concluido) });

    await preencherEEnviar();

    await waitFor(() => expect(push).toHaveBeenCalledWith('/resultado/a1'), { timeout: 3000 });
    await new Promise((r) => setTimeout(r, 80));
    expect(push).toHaveBeenCalledTimes(1);
  });

  it('não navega com 100% em job ainda em andamento', async () => {
    const quase = job({
      status: 'running',
      etapa_atual: 'armazenando',
      etapas_concluidas: ['extraindo', 'chunking', 'embeddings', 'gerando', 'revisando'],
      progresso_percentual: 100,
    });
    const criarPorTexto = vi.fn().mockResolvedValue(job({ job_id: 'j1' }));
    montar({ criarPorTexto, obterJob: vi.fn().mockResolvedValue(quase) });

    await preencherEEnviar();

    expect(await screen.findByText('100%')).toBeInTheDocument();
    await new Promise((r) => setTimeout(r, 80));
    expect(push).not.toHaveBeenCalled();
  });

  it('cancela pelo DELETE e volta ao formulário mesmo se a API rejeitar', async () => {
    const cancelarJob = vi.fn().mockRejectedValue(new Error('falhou'));
    const criarPorTexto = vi.fn().mockResolvedValue(job({ job_id: 'j1' }));
    montar({ criarPorTexto, obterJob: vi.fn().mockResolvedValue(emAndamento('j1')), cancelarJob });

    await preencherEEnviar();
    await screen.findByText('Gerando seu material');

    await userEvent.click(screen.getByRole('button', { name: /cancelar geração/i }));

    expect(cancelarJob).toHaveBeenCalledWith('j1');
    expect(await screen.findByText('O material gerado aparece aqui.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /gerar material/i })).toBeEnabled();
  });
});
