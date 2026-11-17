import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it } from 'vitest';
import { SkinProvider } from '@/features/theme/SkinProvider';
import { useSkin } from '@/features/theme/useSkin';
import { SkinSwitcher } from './SkinSwitcher';

describe('SkinSwitcher', () => {
  beforeEach(() => {
    localStorage.clear();
    useSkin.setState({ skin: 'violeta', modo: 'dark' });
    document.documentElement.dataset.skin = 'violeta';
    document.documentElement.dataset.modo = 'dark';
    document.documentElement.style.colorScheme = 'dark';
  });

  it('aplica a skin no <html> e persiste no localStorage', async () => {
    render(
      <SkinProvider>
        <SkinSwitcher />
      </SkinProvider>,
    );

    await userEvent.click(screen.getByRole('button', { name: /ciano/i }));

    expect(document.documentElement.dataset.skin).toBe('ciano');
    expect(JSON.parse(localStorage.getItem('novamente.skin')!).state.skin).toBe('ciano');
  });

  it('alterna o modo, atualiza o <html> e persiste', async () => {
    render(
      <SkinProvider>
        <SkinSwitcher />
      </SkinProvider>,
    );

    await userEvent.click(screen.getByRole('button', { name: /ativar modo claro/i }));

    expect(document.documentElement.dataset.modo).toBe('light');
    expect(document.documentElement.style.colorScheme).toBe('light');
    expect(JSON.parse(localStorage.getItem('novamente.skin')!).state.modo).toBe('light');

    await userEvent.click(screen.getByRole('button', { name: /ativar modo escuro/i }));
    expect(document.documentElement.dataset.modo).toBe('dark');
  });

  it('anuncia a skin e o modo ativos com aria-pressed', () => {
    render(
      <SkinProvider>
        <SkinSwitcher />
      </SkinProvider>,
    );

    expect(screen.getByRole('button', { name: /violeta/i })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('button', { name: /ciano/i })).toHaveAttribute('aria-pressed', 'false');
    expect(screen.getByRole('button', { name: /ativar modo claro/i })).toHaveAttribute(
      'aria-pressed',
      'false',
    );
  });
});
