import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { LandingPage } from './LandingPage';
import { SkinProvider } from '@/features/theme/SkinProvider';

describe('LandingPage', () => {
  it('apresenta a proposta e os dois CTAs', () => {
    render(
      <SkinProvider>
        <LandingPage />
      </SkinProvider>,
    );
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('material didático');
    expect(screen.getByRole('link', { name: /área da empresa/i })).toHaveAttribute('href', '/empresa/gerar');
    expect(screen.getByRole('link', { name: /sou aluno/i })).toHaveAttribute('href', '/aluno');
    for (const titulo of [/flashcards/i, /quiz/i, /tutorial/i, /resumo executivo/i]) {
      expect(screen.getAllByText(titulo).length).toBeGreaterThan(0);
    }
  });

  it('marca os alvos do tour e as âncoras do header', () => {
    render(
      <SkinProvider>
        <LandingPage />
      </SkinProvider>,
    );
    expect(document.querySelector('[data-tour="landing-hero"]')).not.toBeNull();
    expect(document.querySelector('[data-tour="landing-publicos"]')).not.toBeNull();
    expect(screen.getByRole('link', { name: /como funciona/i })).toHaveAttribute('href', '#como-funciona');
    expect(screen.getByRole('link', { name: /formatos/i })).toHaveAttribute('href', '#formatos');
    expect(screen.getByRole('link', { name: /tecnologia/i })).toHaveAttribute('href', '#tecnologia');
    expect(screen.getByRole('link', { name: /equipe/i })).toHaveAttribute('href', '#equipe');
  });
});
