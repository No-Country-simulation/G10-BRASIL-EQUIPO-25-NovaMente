import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { Logo } from './Logo';

describe('Logo', () => {
  it('linka para a landing e renderiza as variantes escura e clara', () => {
    render(<Logo />);

    const link = screen.getByRole('link', { name: /novamente/i });
    expect(link).toHaveAttribute('href', '/');

    const imagens = screen.getAllByAltText('NovaMente');
    expect(imagens).toHaveLength(2);
    expect(imagens[0]).toHaveAttribute('src', '/brand/logo-header.svg');
    expect(imagens[0]).toHaveClass('logo-para-modo-escuro');
    expect(imagens[1]).toHaveAttribute('src', '/brand/logo-header-light.svg');
    expect(imagens[1]).toHaveClass('logo-para-modo-claro');
  });

  it('respeita um href customizado', () => {
    render(<Logo href="/empresa/gerar" />);
    expect(screen.getByRole('link', { name: /novamente/i })).toHaveAttribute(
      'href',
      '/empresa/gerar',
    );
  });
});
