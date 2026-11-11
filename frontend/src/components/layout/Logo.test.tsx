import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { Logo } from './Logo';

describe('Logo', () => {
  it('linka para a landing e usa o lockup da marca', () => {
    render(<Logo />);

    const link = screen.getByRole('link', { name: /novamente/i });
    expect(link).toHaveAttribute('href', '/');
    expect(screen.getByAltText('NovaMente')).toHaveAttribute('src', '/brand/logo-header.svg');
  });

  it('respeita um href customizado', () => {
    render(<Logo href="/empresa/gerar" />);
    expect(screen.getByRole('link', { name: /novamente/i })).toHaveAttribute(
      'href',
      '/empresa/gerar',
    );
  });
});
