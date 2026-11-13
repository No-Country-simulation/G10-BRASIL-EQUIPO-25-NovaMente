import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { AlunosView } from './AlunosView';
import { ApiProvider } from '@/services/api/ApiProvider';
import type { NovaMenteApi } from '@/services/api/NovaMenteApi';
import type { AlunoResumo, PaginaAlunos } from '@/types/novamente';

const mocks = vi.hoisted(() => ({
  replace: vi.fn(),
  params: new URLSearchParams(),
}));

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: mocks.replace, push: vi.fn() }),
  useSearchParams: () => mocks.params,
}));

const aluno = (over: Partial<AlunoResumo> = {}): AlunoResumo => ({
  aluno_id: 'A1',
  nome: 'Ana Beatriz Silva',
  email: 'ana.silva@exemplo.com',
  status: 'ativo',
  total_materiais: 2,
  criado_em: '2026-10-01T09:00:00Z',
  atualizado_em: '2026-10-01T09:00:00Z',
  ...over,
});

const pagina = (itens: AlunoResumo[] = [aluno()]): PaginaAlunos => ({
  itens,
  pagina: 1,
  tamanho_pagina: 12,
  total: itens.length,
  total_paginas: itens.length > 0 ? 1 : 0,
});

function renderComApi(ui: ReactNode, api: Partial<NovaMenteApi> = {}) {
  const cliente = {
    listarAlunos: vi.fn().mockResolvedValue(pagina()),
    criarAluno: vi.fn().mockResolvedValue(aluno({ aluno_id: 'A2', nome: 'Ana' })),
    atualizarAluno: vi.fn().mockResolvedValue(aluno({ nome: 'Ana Editada' })),
    excluirAluno: vi.fn().mockResolvedValue(undefined),
    ...api,
  } as unknown as NovaMenteApi;
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <ApiProvider client={cliente}>
      <QueryClientProvider client={client}>{ui}</QueryClientProvider>
    </ApiProvider>,
  );
  return { api: cliente, client };
}

beforeEach(() => {
  mocks.replace.mockReset();
  mocks.params = new URLSearchParams();
});

describe('AlunosView', () => {
  it('lista os alunos com as ações de gestão', async () => {
    renderComApi(<AlunosView />);

    expect(await screen.findByText('Ana Beatriz Silva')).toBeInTheDocument();
    expect(screen.getByText('ana.silva@exemplo.com')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /materiais/i })).toHaveAttribute(
      'href',
      '/empresa/alunos/A1',
    );
    expect(screen.getByRole('button', { name: /editar/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /excluir/i })).toBeInTheDocument();
    expect(screen.getByText('2 materiais')).toBeInTheDocument();
  });

  it('cria um aluno pelo diálogo', async () => {
    const criar = vi.fn().mockResolvedValue(aluno({ aluno_id: 'A2', nome: 'Ana' }));
    renderComApi(<AlunosView />, { criarAluno: criar });

    await userEvent.click(await screen.findByRole('button', { name: /novo aluno/i }));
    await userEvent.type(screen.getByLabelText(/nome/i), 'Ana');
    await userEvent.type(screen.getByLabelText(/e-mail/i), 'ana@exemplo.com');
    await userEvent.click(screen.getByRole('button', { name: /salvar/i }));

    await waitFor(() =>
      expect(criar).toHaveBeenCalledWith({
        nome: 'Ana',
        email: 'ana@exemplo.com',
        status: 'ativo',
      }),
    );
    expect(await screen.findByRole('status')).toHaveTextContent('Aluno cadastrado.');
  });

  it('mapeia 409 de e-mail para o campo', async () => {
    const { ErroApi } = await import('@/services/api/erros');
    const criar = vi.fn().mockRejectedValue(
      new ErroApi(
        {
          erro: {
            codigo: 'EMAIL_JA_CADASTRADO',
            mensagem: 'E-mail já cadastrado.',
            campos: { email: 'E-mail já cadastrado.' },
          },
        },
        409,
      ),
    );
    renderComApi(<AlunosView />, {
      listarAlunos: vi.fn().mockResolvedValue(pagina([])),
      criarAluno: criar,
    });

    await userEvent.click(await screen.findByRole('button', { name: /novo aluno/i }));
    await userEvent.type(screen.getByLabelText(/nome/i), 'Ana');
    await userEvent.type(screen.getByLabelText(/e-mail/i), 'ana@exemplo.com');
    await userEvent.click(screen.getByRole('button', { name: /salvar/i }));

    expect(await screen.findByText('E-mail já cadastrado.')).toBeInTheDocument();
    expect(screen.getByLabelText(/e-mail/i)).toHaveAttribute('aria-invalid', 'true');
  });

  it('valida nome e e-mail antes de enviar', async () => {
    const criar = vi.fn();
    renderComApi(<AlunosView />, { listarAlunos: vi.fn().mockResolvedValue(pagina([])), criarAluno: criar });

    await userEvent.click(await screen.findByRole('button', { name: /novo aluno/i }));
    await userEvent.type(screen.getByLabelText(/nome/i), 'An');
    await userEvent.type(screen.getByLabelText(/e-mail/i), 'ana');
    await userEvent.click(screen.getByRole('button', { name: /salvar/i }));

    expect(await screen.findByText('Mínimo de 3 caracteres')).toBeInTheDocument();
    expect(await screen.findByText('E-mail inválido')).toBeInTheDocument();
    expect(criar).not.toHaveBeenCalled();
  });

  it('edita um aluno pelo diálogo', async () => {
    const atualizar = vi.fn().mockResolvedValue(aluno({ nome: 'Ana Editada' }));
    renderComApi(<AlunosView />, { atualizarAluno: atualizar });

    await userEvent.click(await screen.findByRole('button', { name: /editar/i }));
    const dialogo = await screen.findByRole('dialog');
    const campo = within(dialogo).getByLabelText(/nome/i);
    await userEvent.clear(campo);
    await userEvent.type(campo, 'Ana Editada');
    await userEvent.click(within(dialogo).getByRole('button', { name: /salvar/i }));

    await waitFor(() =>
      expect(atualizar).toHaveBeenCalledWith('A1', {
        nome: 'Ana Editada',
        email: 'ana.silva@exemplo.com',
        status: 'ativo',
      }),
    );
    expect(await screen.findByRole('status')).toHaveTextContent('Aluno atualizado.');
  });

  it('exclui com confirmação e avisa sobre vínculos', async () => {
    const excluir = vi.fn().mockResolvedValue(undefined);
    renderComApi(<AlunosView />, { excluirAluno: excluir });

    await userEvent.click(await screen.findByRole('button', { name: /excluir/i }));
    const dialogo = await screen.findByRole('dialog');
    expect(within(dialogo).getByText(/Ana Beatriz Silva/)).toBeInTheDocument();
    expect(within(dialogo).getByText(/vínculos/i)).toBeInTheDocument();
    await userEvent.click(within(dialogo).getByRole('button', { name: /confirmar e excluir/i }));

    await waitFor(() => expect(excluir).toHaveBeenCalledWith('A1'));
    expect(await screen.findByRole('status')).toHaveTextContent('Aluno excluído.');
  });

  it('filtra pelo status refletindo na URL', async () => {
    renderComApi(<AlunosView />);

    await screen.findByText('Ana Beatriz Silva');
    await userEvent.selectOptions(screen.getByLabelText(/todos os status/i), 'inativo');

    expect(mocks.replace).toHaveBeenCalledWith('/empresa/alunos?status=inativo');
  });

  it('mostra vazio quando não há alunos', async () => {
    renderComApi(<AlunosView />, {
      listarAlunos: vi.fn().mockResolvedValue(pagina([])),
    });

    expect(await screen.findByText(/nenhum aluno cadastrado/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /novo aluno/i })).toBeInTheDocument();
  });

  it('mostra erro com retry', async () => {
    renderComApi(<AlunosView />, {
      listarAlunos: vi.fn().mockRejectedValue(new Error('falhou')),
    });

    expect(await screen.findByRole('alert')).toHaveTextContent('inesperado');
    expect(screen.getByRole('button', { name: /tentar novamente/i })).toBeInTheDocument();
  });

  it('pagina pela URL', async () => {
    renderComApi(<AlunosView />, {
      listarAlunos: vi.fn().mockResolvedValue({
        itens: [aluno()],
        pagina: 1,
        tamanho_pagina: 12,
        total: 14,
        total_paginas: 2,
      }),
    });

    await screen.findByText('Ana Beatriz Silva');
    await userEvent.click(screen.getByRole('button', { name: /próxima/i }));

    expect(mocks.replace).toHaveBeenCalledWith('/empresa/alunos?pagina=2');
  });
});
