import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it } from 'vitest';
import { limparArmazenamento } from '@/test/consentimento';
import { ARMAZENAMENTOS } from '@/lib/privacidade';
import { BannerCookies } from './BannerCookies';
import { PoliticaPrivacidade } from './PoliticaPrivacidade';

beforeEach(() => limparArmazenamento());

describe('PoliticaPrivacidade', () => {
  it('traz o título, a versão e as 12 seções ligadas ao sumário', () => {
    render(<PoliticaPrivacidade />);

    expect(
      screen.getByRole('heading', { level: 1, name: 'Política de Privacidade e Cookies' }),
    ).toBeInTheDocument();
    expect(screen.getByText(/Versão 1\.0 · Atualizada em/)).toBeInTheDocument();

    const sumario = screen.getByRole('navigation', { name: 'Neste documento' });
    const links = within(sumario).getAllByRole('link');
    expect(links).toHaveLength(12);
    for (const link of links) {
      const id = link.getAttribute('href')!.slice(1);
      expect(document.getElementById(id)).not.toBeNull();
    }
  });

  it('lista todos os cookies e itens de armazenamento que o app usa', () => {
    render(<PoliticaPrivacidade />);

    for (const item of ARMAZENAMENTOS) {
      expect(screen.getByRole('heading', { level: 3, name: item.nome })).toBeInTheDocument();
    }
    expect(screen.getByRole('heading', { level: 3, name: 'nm_sessao' })).toBeInTheDocument();
    expect(screen.getByText(/cookies de publicidade, de análise de audiência/i)).toBeInTheDocument();
  });

  it('cita os direitos do art. 18, a ANPD e a lei, com links externos seguros', () => {
    render(<PoliticaPrivacidade />);

    expect(screen.getByText(/Revogação do consentimento/)).toBeInTheDocument();
    const lei = screen.getByRole('link', { name: /Lei nº 13\.709\/2018/ });
    expect(lei).toHaveAttribute('href', expect.stringContaining('planalto.gov.br'));
    expect(lei).toHaveAttribute('rel', expect.stringContaining('noopener'));
    expect(screen.getByRole('link', { name: /Autoridade Nacional de Proteção de Dados/ })).toBeInTheDocument();
  });

  it('sem e-mail configurado, aponta para o canal da equipe responsável', () => {
    render(<PoliticaPrivacidade />);

    expect(screen.getByText(/canal de contato informado pela equipe responsável/i)).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: /@/ })).not.toBeInTheDocument();
  });

  it('o botão da seção de cookies reabre o aviso de escolha', async () => {
    window.localStorage.setItem(
      'novamente.consentimento',
      JSON.stringify({ versao: 1, preferencias: true, decidido_em: '2026-11-21T12:00:00Z' }),
    );
    render(
      <>
        <BannerCookies />
        <PoliticaPrivacidade />
      </>,
    );
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: 'Preferências de cookies' }));

    expect(await screen.findByRole('dialog')).toBeInTheDocument();
  });
});
