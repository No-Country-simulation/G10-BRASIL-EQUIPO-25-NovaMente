import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it } from 'vitest';
import { SkinProvider } from '@/features/theme/SkinProvider';
import { useSkin } from '@/features/theme/useSkin';
import { SkinSwitcher } from './SkinSwitcher';

describe('SkinSwitcher', () => {
  beforeEach(() => {
    localStorage.clear();
    useSkin.setState({ skin: 'violeta' });
    document.documentElement.dataset.skin = 'violeta';
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

  it('anuncia a skin ativa com aria-pressed', async () => {
    render(
      <SkinProvider>
        <SkinSwitcher />
      </SkinProvider>,
    );

    expect(screen.getByRole('button', { name: /violeta/i })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('button', { name: /ciano/i })).toHaveAttribute('aria-pressed', 'false');
  });
});
