import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { Cenarios } from './Cenarios';

describe('Cenarios', () => {
  it('oferece os três cenários do edital', () => {
    render(<Cenarios aoDisparar={vi.fn()} />);
    expect(screen.getByRole('button', { name: /iniciante \+ flashcards/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /desenvolvedor \+ quiz/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /gestor \+ resumo executivo/i })).toBeInTheDocument();
  });

  it('dispara o cenário escolhido', async () => {
    const aoDisparar = vi.fn();
    render(<Cenarios aoDisparar={aoDisparar} />);
    await userEvent.click(screen.getByRole('button', { name: /gestor \+ resumo executivo/i }));
    expect(aoDisparar).toHaveBeenCalledWith(
      expect.objectContaining({ perfil: 'Gestor', formato: 'ResumoExecutivo', nivel: 'Executivo' }),
    );
  });

  it('desabilita os chips durante uma geração', () => {
    render(<Cenarios aoDisparar={vi.fn()} desabilitado />);
    expect(screen.getByRole('button', { name: /iniciante \+ flashcards/i })).toBeDisabled();
    expect(screen.getByRole('button', { name: /desenvolvedor \+ quiz/i })).toBeDisabled();
    expect(screen.getByRole('button', { name: /gestor \+ resumo executivo/i })).toBeDisabled();
  });
});
