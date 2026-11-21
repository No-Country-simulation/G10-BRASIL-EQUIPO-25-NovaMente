'use client';

import { MutationCache, QueryCache, QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useState } from 'react';
import { ApiProvider } from '@/services/api/ApiProvider';
import { ErroApi } from '@/services/api/erros';
import { MockProvider } from '@/mocks/MockProvider';

export function Providers({ children }: { children: React.ReactNode }) {
  const [client] = useState(() => {
    // Sessão vencida no meio do uso: qualquer 401 NAO_AUTENTICADO derruba a sessão
    // local e as guardas de rota levam para a tela de entrada.
    const aoFalhar = (erro: unknown) => {
      if (
        erro instanceof ErroApi &&
        erro.status === 401 &&
        erro.problema.erro.codigo === 'NAO_AUTENTICADO'
      ) {
        instancia.setQueryData(['sessao'], null);
      }
    };

    const instancia: QueryClient = new QueryClient({
      queryCache: new QueryCache({ onError: aoFalhar }),
      mutationCache: new MutationCache({ onError: aoFalhar }),
      defaultOptions: {
        queries: {
          retry: (tentativa, erro) => {
            if (erro instanceof ErroApi && erro.status < 500) return false;
            return tentativa < 2;
          },
          staleTime: 30_000,
          refetchOnWindowFocus: false,
        },
      },
    });
    return instancia;
  });

  return (
    <MockProvider>
      <ApiProvider>
        <QueryClientProvider client={client}>{children}</QueryClientProvider>
      </ApiProvider>
    </MockProvider>
  );
}
