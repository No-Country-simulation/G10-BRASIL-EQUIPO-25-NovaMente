import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { HealthBanner } from './HealthBanner';
import { ApiProvider } from '@/services/api/ApiProvider';
import type { NovaMenteApi } from '@/services/api/NovaMenteApi';

function renderizar(health: NovaMenteApi['health']) {
  const api = { health } as unknown as NovaMenteApi;
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <ApiProvider client={api}>
      <QueryClientProvider client={client}>
        <HealthBanner />
      </QueryClientProvider>
    </ApiProvider>,
  );
  return health;
}

describe('HealthBanner', () => {
  it('não renderiza nada quando está tudo ok', async () => {
    const health = renderizar(
      vi.fn().mockResolvedValue({
        status: 'ok',
        versao: '0.1.0-mock',
        oci: 'ok',
        llm: 'ok',
        verificado_em: '2026-10-21T14:00:00Z',
      }),
    );
    await waitFor(() => expect(health).toHaveBeenCalledOnce());
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
  });

  it('mostra banner quando a API está degradada', async () => {
    renderizar(
      vi.fn().mockResolvedValue({
        status: 'degraded',
        versao: '0.1.0-mock',
        oci: 'indisponivel',
        llm: 'ok',
        verificado_em: '2026-10-21T14:00:00Z',
      }),
    );
    const banner = await screen.findByRole('status');
    expect(banner.textContent).toMatch(/oci: indisponivel/i);
  });

  it('não quebra a página quando a consulta de saúde falha', async () => {
    const health = renderizar(vi.fn().mockRejectedValue(new Error('rede fora')));
    await waitFor(() => expect(health).toHaveBeenCalledOnce());
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
  });
});
