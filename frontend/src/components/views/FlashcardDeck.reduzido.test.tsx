import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeAll, describe, expect, it } from 'vitest';
import { FlashcardDeck } from './FlashcardDeck';

// O framer-motion guarda a preferência de motion num singleton de módulo,
// inicializado no primeiro render do arquivo. Por isso este cenário vive em um
// arquivo próprio e o matchMedia é trocado antes de qualquer render.
beforeAll(() => {
  window.matchMedia = ((consulta: string) => ({
    matches: consulta.includes('prefers-reduced-motion'),
    media: consulta,
    onchange: null,
    addEventListener: () => {},
    removeEventListener: () => {},
    addListener: () => {},
    removeListener: () => {},
    dispatchEvent: () => false,
  })) as unknown as typeof window.matchMedia;
});

const itens = [
  { frente: 'Frente 1', verso: 'Verso 1', dica_didatica: 'Dica 1' },
  { frente: 'Frente 2', verso: 'Verso 2' },
];

describe('FlashcardDeck com prefers-reduced-motion', () => {
  it('marca motion reduzido e troca a face sem animação', async () => {
    render(<FlashcardDeck itens={itens} />);

    expect(screen.getByTestId('flashcard-palco')).toHaveAttribute('data-motion', 'reduzido');
    expect(screen.getByText('Frente 1').closest('[data-ativa]')).toHaveStyle({ opacity: '1' });
    expect(screen.getByText('Verso 1').closest('[data-ativa]')).toHaveStyle({ opacity: '0' });

    await userEvent.click(screen.getByRole('button', { name: /mostrar verso/i }));

    // O palco não gira no modo reduzido: a troca é só por opacidade.
    const palco = screen.getByTestId('flashcard-palco');
    expect(palco.style.transform).not.toContain('180deg');
    // framer-motion grava `none` quando a rotação é 0.
    expect(palco.style.transform).toMatch(/^(none|rotateY\(0deg\))?$/);
    expect(screen.getByRole('button', { name: /mostrar frente/i })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByText('Frente 1').closest('[data-ativa]')).toHaveStyle({ opacity: '0' });
    expect(screen.getByText('Verso 1').closest('[data-ativa]')).toHaveStyle({ opacity: '1' });
  });
});
