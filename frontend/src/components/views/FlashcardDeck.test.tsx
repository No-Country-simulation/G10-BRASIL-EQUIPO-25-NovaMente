import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { FlashcardDeck } from './FlashcardDeck';

const itens = [
  { frente: 'Frente 1', verso: 'Verso 1', dica_didatica: 'Dica 1' },
  { frente: 'Frente 2', verso: 'Verso 2' },
  { frente: 'Frente 3', verso: 'Verso 3' },
];

describe('FlashcardDeck', () => {
  it('começa no primeiro cartão, com a frente ativa', () => {
    render(<FlashcardDeck itens={itens} />);
    expect(screen.getByText('1 / 3')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /mostrar verso/i })).toHaveAttribute('aria-pressed', 'false');
    expect(screen.getByText('Frente 1').closest('[data-ativa]')).toHaveAttribute('data-ativa', 'true');
  });

  it('vira o cartão ao clicar e ao teclar Enter', async () => {
    render(<FlashcardDeck itens={itens} />);
    const cartao = screen.getByRole('button', { name: /mostrar verso/i });
    await userEvent.click(cartao);
    expect(screen.getByRole('button', { name: /mostrar frente/i })).toHaveAttribute('aria-pressed', 'true');
    await userEvent.keyboard('{Enter}');
    expect(screen.getByRole('button', { name: /mostrar verso/i })).toHaveAttribute('aria-pressed', 'false');
  });

  it('navega com as setas e reseta o flip', async () => {
    render(<FlashcardDeck itens={itens} />);
    await userEvent.click(screen.getByRole('button', { name: /mostrar verso/i }));
    await userEvent.click(screen.getByRole('button', { name: /próximo/i }));
    expect(screen.getByText('2 / 3')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /mostrar verso/i })).toHaveAttribute('aria-pressed', 'false');
    await userEvent.click(screen.getByRole('button', { name: /anterior/i }));
    expect(screen.getByText('1 / 3')).toBeInTheDocument();
  });

  it('navega por teclado no deck', async () => {
    render(<FlashcardDeck itens={itens} />);
    screen.getByRole('region', { name: /flashcards/i }).focus();
    await userEvent.keyboard('{ArrowRight}');
    expect(screen.getByText('2 / 3')).toBeInTheDocument();
    await userEvent.keyboard('{ArrowLeft}');
    expect(screen.getByText('1 / 3')).toBeInTheDocument();
  });

  it('mostra a dica didática sem exigir o verso e marca motion reduzido', () => {
    render(<FlashcardDeck itens={itens} />);
    expect(screen.getByText('Dica 1')).toBeInTheDocument();
    expect(screen.getByTestId('flashcard-palco')).toHaveAttribute('data-motion', 'completo');
  });

  it('avisa quando o deck vem vazio', () => {
    render(<FlashcardDeck itens={[]} />);
    expect(screen.getByText('Nenhum cartão disponível.')).toBeInTheDocument();
  });
});
