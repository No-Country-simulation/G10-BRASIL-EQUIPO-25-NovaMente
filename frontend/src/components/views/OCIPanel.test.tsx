import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { OCIPanel } from './OCIPanel';

const armazenamento = { bucket: 'novamente', objeto_id: 'a.json', status_upload: 'concluido' as const };
const avaliacao = { ancoragem_fonte_score: 0.98, clareza_pedagogica: 'Alta' as const };

describe('OCIPanel', () => {
  it('mostra score, faixa e dados do bucket', () => {
    render(<OCIPanel armazenamento={armazenamento} avaliacao={avaliacao} />);
    expect(screen.getByText('98%')).toBeInTheDocument();
    expect(screen.getByTestId('score-gauge')).toHaveAttribute('data-faixa', 'alta');
    expect(screen.getByText('novamente')).toBeInTheDocument();
    expect(screen.getByText('a.json')).toBeInTheDocument();
    expect(screen.getByText('Persistido no OCI')).toBeInTheDocument();
  });

  it('avisa quando o upload falhou, sem esconder o conteúdo', () => {
    render(<OCIPanel armazenamento={{ ...armazenamento, status_upload: 'falha' }} avaliacao={avaliacao} />);
    expect(screen.getByText(/não persistido no OCI/i)).toBeInTheDocument();
    expect(screen.getByText('98%')).toBeInTheDocument();
  });

  it('mostra estado neutro quando o OCI não está configurado', () => {
    render(
      <OCIPanel
        armazenamento={armazenamento}
        avaliacao={avaliacao}
        oci={{ configurado: false, mensagem: 'Credenciais ausentes', verificado_em: '2026-10-21T14:00:00Z' }}
      />,
    );
    expect(screen.getByText('OCI não configurado')).toBeInTheDocument();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it('não renderiza bloco vazio de detalhes quando o OCI configurado não traz métricas', () => {
    render(
      <OCIPanel
        armazenamento={armazenamento}
        avaliacao={avaliacao}
        oci={{ configurado: true, verificado_em: '2026-10-21T14:00:00Z' }}
      />,
    );
    expect(screen.queryByText('Objetos')).not.toBeInTheDocument();
    expect(screen.queryByText('Último upload')).not.toBeInTheDocument();
  });
});
