import { render, screen, waitFor } from '@testing-library/react';
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
    const barra = screen.getByRole('progressbar');
    expect(barra).toHaveAttribute('aria-valuenow');
    expect(Number(barra.getAttribute('aria-valuenow'))).toBeCloseTo(33.3, 1);
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

  it('gira o palco com as faces estáticas e descreve a face ativa', async () => {
    render(<FlashcardDeck itens={itens} />);
    const palco = screen.getByTestId('flashcard-palco');
    const frente = screen.getByText('Frente 1').closest('[data-ativa]') as HTMLElement;
    const verso = screen.getByText('Verso 1').closest('[data-ativa]') as HTMLElement;

    expect(palco).toHaveStyle({ transformStyle: 'preserve-3d' });
    expect(frente).toHaveStyle({ transform: 'rotateY(0deg)' });
    expect(verso).toHaveStyle({ transform: 'rotateY(180deg)' });
    expect(palco).toHaveAttribute('aria-describedby', frente.id);

    await userEvent.click(screen.getByRole('button', { name: /mostrar verso/i }));

    // Só o palco anima: a frente e o verso seguem estáticos em 0° e 180°.
    await waitFor(() => expect(palco.style.transform).toContain('rotateY(180deg)'));
    expect(frente.style.transform).toBe('rotateY(0deg)');
    expect(verso.style.transform).toBe('rotateY(180deg)');
    expect(palco).toHaveAttribute('aria-describedby', verso.id);
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
