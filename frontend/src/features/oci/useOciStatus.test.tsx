import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { describe, expect, it, vi } from 'vitest';
import { useOciStatus } from './useOciStatus';
import { ApiProvider } from '@/services/api/ApiProvider';
import { ErroContrato } from '@/services/api/erros';
import type { NovaMenteApi } from '@/services/api/NovaMenteApi';
import type { OciStatus } from '@/types/novamente';

const status: OciStatus = {
  configurado: true,
  bucket: 'novamente',
  regiao: 'sa-saopaulo-1',
  total_objetos: 4,
  verificado_em: '2026-10-21T14:00:00Z',
};

function montar(statusOci: NovaMenteApi['statusOci']) {
  const api = { statusOci } as unknown as NovaMenteApi;
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const wrapper = ({ children }: { children: ReactNode }) => (
    <ApiProvider client={api}>
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    </ApiProvider>
  );
  return { wrapper };
}

describe('useOciStatus', () => {
  it('devolve o status validado pelo schema', async () => {
    const statusOci = vi.fn().mockResolvedValue(status);
    const { wrapper } = montar(statusOci);

    const { result } = renderHook(() => useOciStatus(), { wrapper });

    await waitFor(() => expect(result.current.data).toEqual(status));
    expect(statusOci).toHaveBeenCalledOnce();
  });

  it('lança ErroContrato quando a resposta viola o schema', async () => {
    const statusOci = vi.fn().mockResolvedValue({ configurado: 'sim' } as unknown as OciStatus);
    const { wrapper } = montar(statusOci);

    const { result } = renderHook(() => useOciStatus(), { wrapper });

    await waitFor(() => expect(result.current.error).toBeInstanceOf(ErroContrato));
  });
});
