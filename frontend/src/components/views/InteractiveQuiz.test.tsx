import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { InteractiveQuiz } from './InteractiveQuiz';

const itens = [
  {
    pergunta: 'O que é VCN?',
    opcoes: ['Rede privada', 'Bucket', 'Banco de dados'],
    resposta_correta: 0,
    explicacao: 'VCN é a rede privada da OCI.',
  },
  {
    pergunta: 'O que é NAT Gateway?',
    opcoes: ['Saída privada', 'Entrada pública'],
    resposta_correta: 0,
    explicacao: 'Permite saída sem exposição.',
  },
];

describe('InteractiveQuiz', () => {
  it('mantém Confirmar desabilitado sem seleção', () => {
    render(<InteractiveQuiz itens={itens} />);
    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '50');
    expect(screen.getByRole('button', { name: /confirmar/i })).toBeDisabled();
  });

  it('dá feedback imediato e só então libera a próxima', async () => {
    render(<InteractiveQuiz itens={itens} />);
    await userEvent.click(screen.getByLabelText('Bucket'));
    await userEvent.click(screen.getByRole('button', { name: /confirmar/i }));

    expect(screen.getByText('Resposta incorreta')).toBeInTheDocument();
    expect(screen.getByText('VCN é a rede privada da OCI.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /próxima/i })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /confirmar/i })).not.toBeInTheDocument();
  });

  it('calcula o placar e revisa as erradas', async () => {
    render(<InteractiveQuiz itens={itens} />);

    await userEvent.click(screen.getByLabelText('Rede privada'));
    await userEvent.click(screen.getByRole('button', { name: /confirmar/i }));
    expect(screen.getByText('Resposta correta')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: /próxima/i }));

    await userEvent.click(screen.getByLabelText('Entrada pública'));
    await userEvent.click(screen.getByRole('button', { name: /confirmar/i }));
    await userEvent.click(screen.getByRole('button', { name: /próxima/i }));

    expect(screen.getByText('1 / 2')).toBeInTheDocument();
    expect(screen.getByText(/revisar erradas/i)).toBeInTheDocument();
    expect(screen.getByText('O que é NAT Gateway?')).toBeInTheDocument();
    expect(screen.getByText(/sua resposta/i)).toBeInTheDocument();
  });

  it('anuncia a pergunta como legend de fieldset', () => {
    render(<InteractiveQuiz itens={itens} />);
    expect(screen.getByRole('group', { name: /o que é vcn/i })).toBeInTheDocument();
  });

  it('trava as opções depois de confirmar', async () => {
    render(<InteractiveQuiz itens={itens} />);
    await userEvent.click(screen.getByLabelText('Rede privada'));
    await userEvent.click(screen.getByRole('button', { name: /confirmar/i }));

    expect(screen.getByLabelText('Rede privada')).toBeChecked();
    expect(screen.getByLabelText('Rede privada')).toBeDisabled();
    expect(screen.getByLabelText('Bucket')).toBeDisabled();
    expect(screen.getByLabelText('Banco de dados')).toBeDisabled();
  });

  it('foca a nova pergunta ao avançar e o placar ao finalizar', async () => {
    render(<InteractiveQuiz itens={itens} />);

    await userEvent.click(screen.getByLabelText('Rede privada'));
    await userEvent.click(screen.getByRole('button', { name: /confirmar/i }));
    await userEvent.click(screen.getByRole('button', { name: /próxima/i }));
    expect(screen.getByText('O que é NAT Gateway?')).toHaveFocus();

    await userEvent.click(screen.getByLabelText('Saída privada'));
    await userEvent.click(screen.getByRole('button', { name: /confirmar/i }));
    await userEvent.click(screen.getByRole('button', { name: /próxima/i }));
    expect(screen.getByRole('heading', { name: /placar/i })).toHaveFocus();
  });

  it('permite refazer depois do placar e zera as respostas', async () => {
    render(<InteractiveQuiz itens={[{ ...itens[0] }]} />);
    await userEvent.click(screen.getByLabelText('Rede privada'));
    await userEvent.click(screen.getByRole('button', { name: /confirmar/i }));
    await userEvent.click(screen.getByRole('button', { name: /próxima/i }));
    expect(screen.getByText('1 / 1')).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: /refazer/i }));

    expect(screen.getByText('O que é VCN?')).toHaveFocus();
    expect(screen.getByRole('button', { name: /confirmar/i })).toBeDisabled();
    expect(screen.queryByText('1 / 1')).not.toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: /placar/i })).not.toBeInTheDocument();

    // Uma nova rodada começa do zero: o placar reflete só as respostas novas.
    await userEvent.click(screen.getByLabelText('Bucket'));
    await userEvent.click(screen.getByRole('button', { name: /confirmar/i }));
    await userEvent.click(screen.getByRole('button', { name: /próxima/i }));
    expect(screen.getByText('0 / 1')).toBeInTheDocument();
  });

  it('mostra estado vazio quando não há perguntas', () => {
    render(<InteractiveQuiz itens={[]} />);
    expect(screen.getByText('Nenhuma pergunta disponível.')).toBeInTheDocument();
  });
});
