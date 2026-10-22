import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { JobProgress } from './JobProgress';
import type { JobResposta } from '@/types/novamente';

const job = (over: Partial<JobResposta> = {}): JobResposta => ({
  job_id: 'j1',
  status: 'running',
  etapa_atual: 'embeddings',
  etapas_concluidas: ['extraindo', 'chunking'],
  progresso_percentual: 45,
  iniciado_em: '2026-10-21T14:02:11Z',
  atualizado_em: '2026-10-21T14:02:38Z',
  ...over,
});

describe('JobProgress', () => {
  it('lista as seis etapas e marca a atual', () => {
    render(<JobProgress job={job()} estourou={false} aoCancelar={vi.fn()} aoTentarNovamente={vi.fn()} />);
    expect(screen.getByText('Extraindo texto')).toBeInTheDocument();
    expect(screen.getByText('Salvando no OCI')).toBeInTheDocument();
    expect(screen.getByText('Gerando embeddings').closest('li')).toHaveAttribute('aria-current', 'step');
    expect(screen.getByText('45%')).toBeInTheDocument();
  });

  it('nunca deixa o progresso regredir', () => {
    const { rerender } = render(
      <JobProgress job={job({ progresso_percentual: 60 })} estourou={false} aoCancelar={vi.fn()} aoTentarNovamente={vi.fn()} />,
    );
    expect(screen.getByText('60%')).toBeInTheDocument();
    rerender(<JobProgress job={job({ progresso_percentual: 30 })} estourou={false} aoCancelar={vi.fn()} aoTentarNovamente={vi.fn()} />);
    expect(screen.getByText('60%')).toBeInTheDocument();
    expect(screen.queryByText('30%')).not.toBeInTheDocument();
  });

  it('não marca etapa nenhuma em job na fila e, ao iniciar, só a etapa atual aparece', () => {
    const props = { estourou: false, aoCancelar: vi.fn(), aoTentarNovamente: vi.fn() };
    const { rerender } = render(
      <JobProgress
        job={job({ status: 'queued', etapa_atual: null, etapas_concluidas: [], progresso_percentual: 0 })}
        {...props}
      />,
    );
    expect(document.querySelectorAll('li[aria-current="step"]')).toHaveLength(0);
    expect(screen.getAllByRole('listitem').filter((li) => li.querySelector('.lucide-check'))).toHaveLength(0);

    rerender(
      <JobProgress
        job={job({ status: 'running', etapa_atual: 'extraindo', etapas_concluidas: [], progresso_percentual: 15 })}
        {...props}
      />,
    );
    expect(screen.getByText('Extraindo texto').closest('li')).toHaveAttribute('aria-current', 'step');
    expect(screen.getAllByRole('listitem').filter((li) => li.querySelector('.lucide-check'))).toHaveLength(0);
  });

  it('mostra falha com mensagem e request_id, e permite tentar de novo', async () => {
    const aoTentarNovamente = vi.fn();
    render(
      <JobProgress
        job={job({
          status: 'failed',
          etapa_atual: null,
          erro: { codigo: 'DOCUMENTO_ILEGIVEL', mensagem: 'PDF sem texto.', request_id: 'req-1' },
        })}
        estourou={false}
        aoCancelar={vi.fn()}
        aoTentarNovamente={aoTentarNovamente}
      />,
    );
    expect(screen.getByText('PDF sem texto.')).toBeInTheDocument();
    expect(screen.getByText(/req-1/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: /tentar novamente/i }));
    expect(aoTentarNovamente).toHaveBeenCalled();
  });

  it('mostra mensagem de timeout', () => {
    render(<JobProgress job={job()} estourou aoCancelar={vi.fn()} aoTentarNovamente={vi.fn()} />);
    expect(screen.getByText(/passou de 5 minutos/i)).toBeInTheDocument();
  });

  it('expõe o valor da barra e a etapa atual em aria-valuetext', () => {
    render(<JobProgress job={job()} estourou={false} aoCancelar={vi.fn()} aoTentarNovamente={vi.fn()} />);
    const barra = screen.getByRole('progressbar');
    expect(barra).toHaveAttribute('aria-valuenow', '45');
    expect(barra).toHaveAttribute('aria-valuetext', '45%, etapa Gerando embeddings');
  });

  it('não reanuncia a mensagem livre quando o poll só troca job.mensagem', () => {
    const props = { estourou: false, aoCancelar: vi.fn(), aoTentarNovamente: vi.fn() };
    const { rerender } = render(<JobProgress job={job({ mensagem: 'Processando lote 1 de 3.' })} {...props} />);
    const regiao = document.querySelector('[aria-live="polite"]') as HTMLElement;
    expect(regiao.textContent).toBe('Etapa atual: Gerando embeddings');
    expect(screen.getByText('Processando lote 1 de 3.')).toBeInTheDocument();

    rerender(<JobProgress job={job({ mensagem: 'Processando lote 2 de 3.' })} {...props} />);

    expect(regiao.textContent).toBe('Etapa atual: Gerando embeddings');
    expect(screen.queryByText('Processando lote 1 de 3.')).not.toBeInTheDocument();
    expect(screen.getByText('Processando lote 2 de 3.')).toBeInTheDocument();
  });

  it('cancela pelo botão', async () => {
    const aoCancelar = vi.fn();
    render(<JobProgress job={job()} estourou={false} aoCancelar={aoCancelar} aoTentarNovamente={vi.fn()} />);
    await userEvent.click(screen.getByRole('button', { name: /cancelar geração/i }));
    expect(aoCancelar).toHaveBeenCalled();
  });
});
