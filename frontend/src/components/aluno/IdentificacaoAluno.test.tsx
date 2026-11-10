import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { AreaAluno } from './AreaAluno';
import { CHAVE_IDENTIDADE_ALUNO } from '@/features/aluno/useIdentidadeAluno';
import { M } from '@/lib/mensagens';
import { ApiProvider } from '@/services/api/ApiProvider';
import { ErroApi } from '@/services/api/erros';
import type { NovaMenteApi } from '@/services/api/NovaMenteApi';
import type {
  IdentificacaoAlunoItem,
  ItemCatalogoAluno,
  PaginaCatalogoAluno,
} from '@/types/novamente';

const mocks = vi.hoisted(() => ({
  replace: vi.fn(),
  push: vi.fn(),
  params: new URLSearchParams(),
}));

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: mocks.replace, push: mocks.push }),
  useSearchParams: () => mocks.params,
}));

const identificacao = (): IdentificacaoAlunoItem[] => [
  { aluno_id: 'A1', nome: 'Ana Beatriz' },
  { aluno_id: 'A2', nome: 'Bruno Carvalho' },
];

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

function renderArea(api: Partial<NovaMenteApi> = {}) {
  const cliente = {
    listarIdentificacaoAluno: vi.fn().mockResolvedValue(identificacao()),
    listarCatalogoAluno: vi.fn().mockResolvedValue(paginaCatalogo()),
    ...api,
  } as unknown as NovaMenteApi;
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <ApiProvider client={cliente}>
      <QueryClientProvider client={client}>
        <AreaAluno />
      </QueryClientProvider>
    </ApiProvider>,
  );
  return { api: cliente };
}

beforeEach(() => {
  mocks.replace.mockReset();
  mocks.push.mockReset();
  mocks.params = new URLSearchParams();
  window.localStorage.clear();
});

describe('AreaAluno / identificação', () => {
  it('identifica, persiste e mostra o catálogo', async () => {
    renderArea();

    expect(
      await screen.findByRole('heading', { name: 'Quem está estudando?' }),
    ).toBeInTheDocument();
    expect(screen.getByText(M.aluno.identificacao.avisoSemSenha)).toBeInTheDocument();
    expect(screen.queryByText(/ana\.silva@/)).not.toBeInTheDocument();

    await userEvent.click(
      await screen.findByRole('button', {
        name: M.aluno.identificacao.selecionar('Ana Beatriz'),
      }),
    );
    await userEvent.click(screen.getByRole('button', { name: M.aluno.identificacao.entrar }));

    expect(await screen.findByText('Material de VCN')).toBeInTheDocument();
    expect(window.localStorage.getItem(CHAVE_IDENTIDADE_ALUNO)).toContain('A1');
  });

  it('filtra a lista de alunos pelo nome', async () => {
    renderArea();

    await screen.findByRole('button', {
      name: M.aluno.identificacao.selecionar('Ana Beatriz'),
    });
    await userEvent.type(screen.getByLabelText(M.aluno.identificacao.busca), 'bru');

    expect(
      screen.queryByRole('button', {
        name: M.aluno.identificacao.selecionar('Ana Beatriz'),
      }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: M.aluno.identificacao.selecionar('Bruno Carvalho') }),
    ).toBeInTheDocument();
  });

  it('mostra vazio com link para a área da empresa', async () => {
    renderArea({ listarIdentificacaoAluno: vi.fn().mockResolvedValue([]) });

    expect(await screen.findByText(M.aluno.identificacao.vazio)).toBeInTheDocument();
    expect(
      screen.getByRole('link', { name: M.aluno.identificacao.vazioCta }),
    ).toHaveAttribute('href', '/empresa/alunos');
  });

  it('mostra erro com retry', async () => {
    renderArea({
      listarIdentificacaoAluno: vi.fn().mockRejectedValue(new Error('falhou')),
    });

    expect(await screen.findByRole('alert')).toHaveTextContent('inesperado');
    expect(
      screen.getByRole('button', { name: /tentar novamente/i }),
    ).toBeInTheDocument();
  });

  it('limpa a identidade e avisa quando o catálogo responde 403', async () => {
    window.localStorage.setItem(
      CHAVE_IDENTIDADE_ALUNO,
      JSON.stringify({ aluno_id: 'A1', nome: 'Ana Beatriz' }),
    );
    renderArea({
      listarCatalogoAluno: vi.fn().mockRejectedValue(
        new ErroApi(
          { erro: { codigo: 'ALUNO_INATIVO', mensagem: 'Aluno inativo.' } },
          403,
        ),
      ),
    });

    expect(await screen.findByText(M.aluno.catalogo.sessaoInvalida)).toBeInTheDocument();
    expect(
      screen.getByRole('heading', { name: 'Quem está estudando?' }),
    ).toBeInTheDocument();
    expect(window.localStorage.getItem(CHAVE_IDENTIDADE_ALUNO)).toBeNull();
  });
});
