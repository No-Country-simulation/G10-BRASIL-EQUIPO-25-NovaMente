import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { CatalogoAlunoView } from './CatalogoAlunoView';
import type { IdentidadeAluno } from '@/features/aluno/useIdentidadeAluno';
import { M } from '@/lib/mensagens';
import { ApiProvider } from '@/services/api/ApiProvider';
import { ErroApi } from '@/services/api/erros';
import type { NovaMenteApi } from '@/services/api/NovaMenteApi';
import type { ItemCatalogoAluno, PaginaCatalogoAluno } from '@/types/novamente';

const mocks = vi.hoisted(() => ({
  replace: vi.fn(),
  push: vi.fn(),
  params: new URLSearchParams(),
}));

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: mocks.replace, push: mocks.push }),
  useSearchParams: () => mocks.params,
}));

const aluno: IdentidadeAluno = { aluno_id: 'A1', nome: 'Ana Beatriz' };

const itemCatalogo = (over: Partial<ItemCatalogoAluno> = {}): ItemCatalogoAluno => ({
  material_id: 'M1',
  titulo: 'Material de VCN',
  documento_titulo: 'Introdução à VCN',
  formato: 'Flashcards',
  perfil: 'Iniciante',
  nivel: 'Didatico',
  tempo_estimado_estudo_minutos: 5,
  criado_em: '2026-10-01T09:00:00Z',
  conceitos_chave: ['VCN', 'Sub-redes'],
  ...over,
});

const paginaCatalogo = (itens: ItemCatalogoAluno[] = [itemCatalogo()]): PaginaCatalogoAluno => ({
  itens,
  pagina: 1,
  tamanho_pagina: 12,
  total: itens.length,
  total_paginas: itens.length > 0 ? 1 : 0,
});

function renderCatalogo(
  onSessaoInvalida = vi.fn(),
  api: Partial<NovaMenteApi> = {},
) {
  const cliente = {
    listarCatalogoAluno: vi.fn().mockResolvedValue(paginaCatalogo()),
    ...api,
  } as unknown as NovaMenteApi;
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <ApiProvider client={cliente}>
      <QueryClientProvider client={client}>
        <CatalogoAlunoView aluno={aluno} onSessaoInvalida={onSessaoInvalida} />
      </QueryClientProvider>
    </ApiProvider>,
  );
  return { api: cliente, onSessaoInvalida };
}

beforeEach(() => {
  mocks.replace.mockReset();
  mocks.push.mockReset();
  mocks.params = new URLSearchParams();
});

describe('CatalogoAlunoView', () => {
  it('cumprimenta o aluno e mostra os campos do card', async () => {
    renderCatalogo();

    expect(
      await screen.findByRole('heading', { name: /olá, ana beatriz/i }),
    ).toBeInTheDocument();
    expect(await screen.findByText('Material de VCN')).toBeInTheDocument();
    expect(screen.getByText('Introdução à VCN')).toBeInTheDocument();
    expect(screen.getAllByText('Flashcards').length).toBeGreaterThan(0);
    expect(screen.getAllByText('VCN').length).toBeGreaterThan(0);
    expect(screen.getByText(/5 min de estudo/i)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /estudar/i })).toHaveAttribute(
      'href',
      '/aluno/materiais/M1',
    );
  });

  it('reflete o filtro de formato na URL', async () => {
    renderCatalogo();

    await screen.findByText('Material de VCN');
    await userEvent.selectOptions(screen.getByLabelText(M.aluno.catalogo.todosFormatos), 'Quiz');

    expect(mocks.replace).toHaveBeenCalledWith('/aluno?formato=Quiz');
  });

  it('busca com debounce e sincroniza a URL', async () => {
    renderCatalogo();

    await screen.findByText('Material de VCN');
    await userEvent.type(screen.getByLabelText(M.aluno.catalogo.busca), 'vcn');

    await waitFor(() => expect(mocks.replace).toHaveBeenCalledWith('/aluno?q=vcn'), {
      timeout: 1_500,
    });
  });

  it('pagina pela URL', async () => {
    renderCatalogo(vi.fn(), {
      listarCatalogoAluno: vi.fn().mockResolvedValue({
        ...paginaCatalogo(),
        total: 14,
        total_paginas: 2,
      }),
    });

    await screen.findByText('Material de VCN');
    await userEvent.click(screen.getByRole('button', { name: M.aluno.catalogo.proxima }));

    expect(mocks.replace).toHaveBeenCalledWith('/aluno?pagina=2');
  });

  it('mostra vazio quando o aluno não tem materiais', async () => {
    renderCatalogo(vi.fn(), {
      listarCatalogoAluno: vi.fn().mockResolvedValue(paginaCatalogo([])),
    });

    expect(await screen.findByText(M.aluno.catalogo.vazio)).toBeInTheDocument();
  });

  it('mostra vazio com filtros e permite limpar', async () => {
    mocks.params = new URLSearchParams('q=inexistente');
    renderCatalogo(vi.fn(), {
      listarCatalogoAluno: vi.fn().mockResolvedValue(paginaCatalogo([])),
    });

    expect(await screen.findByText(M.aluno.catalogo.vazioFiltros)).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: M.aluno.catalogo.limparFiltros }));

    expect(mocks.replace).toHaveBeenCalledWith('/aluno');
  });

  it('mostra erro com retry', async () => {
    renderCatalogo(vi.fn(), {
      listarCatalogoAluno: vi.fn().mockRejectedValue(new Error('falhou')),
    });

    expect(await screen.findByRole('alert')).toHaveTextContent('inesperado');
    expect(
      screen.getByRole('button', { name: /tentar novamente/i }),
    ).toBeInTheDocument();
  });

  it.each([
    ['ALUNO_INATIVO', 403],
    ['ALUNO_NAO_ENCONTRADO', 404],
  ])('avisa a sessão inválida em %s', async (codigo, status) => {
    const onSessaoInvalida = vi.fn();
    renderCatalogo(onSessaoInvalida, {
      listarCatalogoAluno: vi.fn().mockRejectedValue(
        new ErroApi({ erro: { codigo, mensagem: 'Sessão inválida.' } } as never, status),
      ),
    });

    await waitFor(() =>
      expect(onSessaoInvalida).toHaveBeenCalledWith(M.aluno.catalogo.sessaoInvalida),
    );
  });
});
