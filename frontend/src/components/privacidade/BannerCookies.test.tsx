import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it } from 'vitest';
import { limparArmazenamento, semearConsentimento } from '@/test/consentimento';
import { CHAVE_CONSENTIMENTO } from '@/features/privacidade/armazenamento';
import { BannerCookies } from './BannerCookies';
import { BotaoPreferenciasCookies } from './BotaoPreferenciasCookies';

function consentimentoSalvo() {
  const bruto = window.localStorage.getItem(CHAVE_CONSENTIMENTO);
  return bruto ? (JSON.parse(bruto) as { preferencias: boolean; versao: number }) : null;
}

beforeEach(() => limparArmazenamento());

describe('BannerCookies', () => {
  it('aparece para quem ainda não escolheu, com o link da política', async () => {
    render(<BannerCookies />);

    const dialogo = await screen.findByRole('dialog', { name: /privacidade em primeiro lugar/i });
    expect(dialogo.textContent).toMatch(/não usamos cookies de publicidade/i);
    expect(screen.getByRole('link', { name: /política de privacidade e cookies/i })).toHaveAttribute(
      'href',
      '/privacidade',
    );
    expect(screen.getByRole('button', { name: 'Somente necessários' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Aceitar preferências' })).toBeInTheDocument();
  });

  it('não aparece para quem já escolheu', async () => {
    semearConsentimento(false);

    render(<BannerCookies />);

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  });

  it('aceitar guarda a escolha e esconde o aviso', async () => {
    render(<BannerCookies />);

    await userEvent.click(await screen.findByRole('button', { name: 'Aceitar preferências' }));

    expect(consentimentoSalvo()).toMatchObject({ preferencias: true });
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('"somente necessários" guarda a recusa e leva o que estava guardado para a sessão', async () => {
    window.sessionStorage.setItem('novamente.skin', '{"state":{"skin":"ciano"}}');
    render(<BannerCookies />);

    await userEvent.click(await screen.findByRole('button', { name: 'Somente necessários' }));

    expect(consentimentoSalvo()).toMatchObject({ preferencias: false });
    expect(window.localStorage.getItem('novamente.skin')).toBeNull();
    expect(window.sessionStorage.getItem('novamente.skin')).not.toBeNull();
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('personalizar mostra as categorias com as preferências desligadas por padrão', async () => {
    render(<BannerCookies />);

    await userEvent.click(await screen.findByRole('button', { name: 'Personalizar' }));

    expect(screen.getByText('Sempre ativos')).toBeInTheDocument();
    const interruptor = screen.getByRole('switch', { name: 'Preferências' });
    expect(interruptor).toHaveAttribute('aria-checked', 'false');
    expect(screen.queryByRole('button', { name: 'Aceitar preferências' })).not.toBeInTheDocument();

    await userEvent.click(interruptor);
    expect(interruptor).toHaveAttribute('aria-checked', 'true');
    await userEvent.click(screen.getByRole('button', { name: 'Salvar minhas escolhas' }));

    expect(consentimentoSalvo()).toMatchObject({ preferencias: true });
  });

  it('salvar sem ligar o interruptor registra a recusa', async () => {
    render(<BannerCookies />);

    await userEvent.click(await screen.findByRole('button', { name: 'Personalizar' }));
    await userEvent.click(screen.getByRole('button', { name: 'Salvar minhas escolhas' }));

    expect(consentimentoSalvo()).toMatchObject({ preferencias: false });
  });

  it('"voltar" recolhe as categorias sem gravar nada', async () => {
    render(<BannerCookies />);

    await userEvent.click(await screen.findByRole('button', { name: 'Personalizar' }));
    await userEvent.click(screen.getByRole('button', { name: 'Voltar' }));

    expect(consentimentoSalvo()).toBeNull();
    expect(screen.getByRole('button', { name: 'Aceitar preferências' })).toBeInTheDocument();
  });

  it('o botão do rodapé reabre o aviso com a escolha atual e permite revogar', async () => {
    semearConsentimento(true);
    window.localStorage.setItem('novamente.skin', '{"state":{"skin":"ciano"}}');
    render(
      <>
        <BannerCookies />
        <BotaoPreferenciasCookies />
      </>,
    );
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: 'Preferências de cookies' }));

    const interruptor = await screen.findByRole('switch', { name: 'Preferências' });
    expect(interruptor).toHaveAttribute('aria-checked', 'true');

    await userEvent.click(interruptor);
    await userEvent.click(screen.getByRole('button', { name: 'Salvar minhas escolhas' }));

    expect(consentimentoSalvo()).toMatchObject({ preferencias: false });
    // Revogou: nada de preferência guardada entre visitas.
    expect(window.localStorage.getItem('novamente.skin')).toBeNull();
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('cancelar e Esc fecham o aviso reaberto sem mudar a escolha', async () => {
    semearConsentimento(true);
    render(
      <>
        <BannerCookies />
        <BotaoPreferenciasCookies />
      </>,
    );

    await userEvent.click(screen.getByRole('button', { name: 'Preferências de cookies' }));
    await userEvent.click(await screen.findByRole('button', { name: 'Cancelar' }));
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: 'Preferências de cookies' }));
    await screen.findByRole('dialog');
    await userEvent.keyboard('{Escape}');
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(consentimentoSalvo()).toMatchObject({ preferencias: true });
  });

  it('pede a escolha de novo quando a versão do texto muda', async () => {
    window.localStorage.setItem(
      CHAVE_CONSENTIMENTO,
      JSON.stringify({ versao: 0, preferencias: true, decidido_em: '2026-01-01T00:00:00Z' }),
    );

    render(<BannerCookies />);

    expect(await screen.findByRole('dialog')).toBeInTheDocument();
  });
});
