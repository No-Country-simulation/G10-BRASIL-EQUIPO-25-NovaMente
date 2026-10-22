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

  it('cancela pelo botão', async () => {
    const aoCancelar = vi.fn();
    render(<JobProgress job={job()} estourou={false} aoCancelar={aoCancelar} aoTentarNovamente={vi.fn()} />);
    await userEvent.click(screen.getByRole('button', { name: /cancelar geração/i }));
    expect(aoCancelar).toHaveBeenCalled();
  });
});
