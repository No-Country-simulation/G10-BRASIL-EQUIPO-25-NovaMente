import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { HistoricoView } from './HistoricoView';
import { ApiProvider } from '@/services/api/ApiProvider';
import type { NovaMenteApi } from '@/services/api/NovaMenteApi';

const mocks = vi.hoisted(() => ({
  replace: vi.fn(),
  params: new URLSearchParams(),
}));

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: mocks.replace, push: vi.fn() }),
  useSearchParams: () => mocks.params,
}));

const resumo = (i: number) => ({
  adaptacao_id: `id-${i}`,
  criado_em: '2026-10-21T14:00:00Z',
  documento: { titulo: `Documento ${i}`, origem: 'texto' as const },
  perfil_aplicado: 'Iniciante' as const,
  formato_gerado: 'Flashcards' as const,
  nivel_detalhe_aplicado: 'Didatico' as const,
  tempo_estimado_estudo_minutos: 5,
  ancoragem_fonte_score: 0.95,
  status_upload: 'concluido' as const,
  conceitos_chave: ['VCN'],
});

function renderizar(listar: NovaMenteApi['listar']) {
  const api = { listar } as unknown as NovaMenteApi;
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const arvore = () => (
    <ApiProvider client={api}>
      <QueryClientProvider client={client}>
        <HistoricoView />
      </QueryClientProvider>
    </ApiProvider>
  );
  const { rerender } = render(arvore());
  return { listar, rerender: () => rerender(arvore()) };
}

beforeEach(() => {
  mocks.replace.mockReset();
  mocks.params = new URLSearchParams();
});

describe('HistoricoView', () => {
  it('lista os materiais da página', async () => {
    renderizar(
      vi.fn().mockResolvedValue({
        itens: [resumo(1), resumo(2)],
        pagina: 1,
        tamanho_pagina: 12,
        total: 2,
        total_paginas: 1,
      }),
    );
    expect(await screen.findByText('Documento 1')).toBeInTheDocument();
    expect(screen.getByText('Documento 2')).toBeInTheDocument();
  });

  it('mostra estado vazio com CTA', async () => {
    renderizar(vi.fn().mockResolvedValue({ itens: [], pagina: 1, tamanho_pagina: 12, total: 0, total_paginas: 0 }));
    expect(await screen.findByText(/nenhum material gerado ainda/i)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /gerar o primeiro material/i })).toHaveAttribute('href', '/');
  });

  it('pagina pela URL', async () => {
    renderizar(
      vi.fn().mockResolvedValue({
        itens: Array.from({ length: 12 }, (_, i) => resumo(i)),
        pagina: 1,
        tamanho_pagina: 12,
        total: 14,
        total_paginas: 2,
      }),
    );
    await screen.findByText('Documento 0');
    await userEvent.click(screen.getByRole('button', { name: /próxima/i }));
    expect(mocks.replace).toHaveBeenCalledWith('/historico?pagina=2');
  });

  it('filtra por formato na URL', async () => {
    renderizar(
      vi.fn().mockResolvedValue({ itens: [resumo(1)], pagina: 1, tamanho_pagina: 12, total: 1, total_paginas: 1 }),
    );
    await screen.findByText('Documento 1');
    await userEvent.selectOptions(screen.getByLabelText(/todos os formatos/i), 'Quiz');
    await waitFor(() => expect(mocks.replace).toHaveBeenCalledWith('/historico?formato=Quiz'));
  });

  it('mostra erro com retry', async () => {
    renderizar(vi.fn().mockRejectedValue(new Error('falhou')));
    expect(await screen.findByRole('alert')).toHaveTextContent('inesperado');
    expect(screen.getByRole('button', { name: /tentar novamente/i })).toBeInTheDocument();
  });

  it('linka cada card para o resultado', async () => {
    renderizar(
      vi.fn().mockResolvedValue({ itens: [resumo(1)], pagina: 1, tamanho_pagina: 12, total: 1, total_paginas: 1 }),
    );
    const link = await screen.findByRole('link', { name: /documento 1/i });
    expect(link).toHaveAttribute('href', '/resultado/id-1');
  });

  it('não mostra paginação quando total_paginas é 0', async () => {
    renderizar(
      vi.fn().mockResolvedValue({ itens: [resumo(1)], pagina: 1, tamanho_pagina: 12, total: 0, total_paginas: 0 }),
    );
    await screen.findByText('Documento 1');
    expect(screen.queryByRole('button', { name: /próxima/i })).not.toBeInTheDocument();
  });

  it('busca com debounce de 300 ms', async () => {
    renderizar(
      vi.fn().mockResolvedValue({ itens: [resumo(1)], pagina: 1, tamanho_pagina: 12, total: 1, total_paginas: 1 }),
    );
    await screen.findByText('Documento 1');

    fireEvent.change(screen.getByLabelText(/buscar por título ou conceito/i), {
      target: { value: 'vcn' },
    });

    expect(mocks.replace).not.toHaveBeenCalled();
    await waitFor(() => expect(mocks.replace).toHaveBeenCalledWith('/historico?q=vcn'), { timeout: 1_500 });
  });

  it('descarta a busca pendente quando a URL muda por navegação', async () => {
    const { rerender } = renderizar(
      vi.fn().mockResolvedValue({ itens: [resumo(1)], pagina: 1, tamanho_pagina: 12, total: 1, total_paginas: 1 }),
    );
    await screen.findByText('Documento 1');

    vi.useFakeTimers();
    try {
      const campo = screen.getByLabelText(/buscar por título ou conceito/i);
      fireEvent.change(campo, { target: { value: 'rascunho' } });

      mocks.params = new URLSearchParams('q=outro');
      await act(async () => {
        rerender();
      });

      expect(campo).toHaveValue('outro');

      act(() => {
        vi.advanceTimersByTime(350);
      });

      expect(mocks.replace).not.toHaveBeenCalled();
    } finally {
      vi.useRealTimers();
    }
  });

  it('ignora formato, perfil e página inválidos da URL', async () => {
    mocks.params = new URLSearchParams('formato=Inexistente&perfil=Inexistente&pagina=abc');
    const listar = vi
      .fn()
      .mockResolvedValue({ itens: [resumo(1)], pagina: 1, tamanho_pagina: 12, total: 1, total_paginas: 1 });
    renderizar(listar);

    await screen.findByText('Documento 1');
    expect(listar).toHaveBeenCalledWith({
      pagina: 1,
      tamanho_pagina: 12,
      formato: undefined,
      perfil: undefined,
      q: '',
    });
    expect(screen.getByLabelText(/todos os formatos/i)).toHaveValue('');
    expect(screen.getByLabelText(/todos os perfis/i)).toHaveValue('');
  });

  it('mostra paginação quando a página está fora do intervalo', async () => {
    mocks.params = new URLSearchParams('pagina=99');
    renderizar(
      vi.fn().mockResolvedValue({ itens: [], pagina: 99, tamanho_pagina: 12, total: 40, total_paginas: 4 }),
    );

    expect(await screen.findByText('Página 99 de 4')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /anterior/i })).toBeEnabled();
    expect(screen.getByRole('button', { name: /próxima/i })).toBeDisabled();
    expect(screen.queryByText(/nenhum material gerado ainda/i)).not.toBeInTheDocument();
  });

  it('mostra vazio filtrado com botão de limpar filtros', async () => {
    mocks.params = new URLSearchParams('formato=Quiz&q=vcn');
    renderizar(vi.fn().mockResolvedValue({ itens: [], pagina: 1, tamanho_pagina: 12, total: 0, total_paginas: 0 }));

    expect(await screen.findByText(/nenhum resultado para os filtros/i)).toBeInTheDocument();
    expect(screen.queryByText(/nenhum material gerado ainda/i)).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: /limpar filtros/i }));
    expect(mocks.replace).toHaveBeenCalledWith('/historico');
  });
});
