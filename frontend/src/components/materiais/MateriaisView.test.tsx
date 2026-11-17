import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MateriaisView } from './MateriaisView';
import { ApiProvider } from '@/services/api/ApiProvider';
import type { NovaMenteApi } from '@/services/api/NovaMenteApi';
import type { MaterialResumo, PaginaMateriais } from '@/types/novamente';

const mocks = vi.hoisted(() => ({
  replace: vi.fn(),
  params: new URLSearchParams(),
}));

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: mocks.replace, push: vi.fn() }),
  useSearchParams: () => mocks.params,
}));

const material = (over: Partial<MaterialResumo> = {}): MaterialResumo => ({
  material_id: 'M1',
  adaptacao_id: 'A1',
  titulo: 'Dominando Redes na Nuvem',
  documento_titulo: 'Introdução à VCN',
  perfil: 'Iniciante',
  formato: 'Flashcards',
  nivel: 'Didatico',
  nicho: 'Geral',
  visibilidade: 'rascunho',
  tempo_estimado_estudo_minutos: 5,
  ancoragem_fonte_score: 0.98,
  status_upload: 'concluido',
  criado_em: '2026-10-21T14:02:11Z',
  atualizado_em: '2026-10-21T14:02:11Z',
  ...over,
});

const pagina = (itens: MaterialResumo[] = [material()]): PaginaMateriais => ({
  itens,
  pagina: 1,
  tamanho_pagina: 12,
  total: itens.length,
  total_paginas: itens.length > 0 ? 1 : 0,
});

function renderComApi(ui: ReactNode, api: Partial<NovaMenteApi> = {}) {
  const cliente = {
    listarMateriais: vi.fn().mockResolvedValue(pagina()),
    atualizarMaterial: vi.fn().mockResolvedValue(material({ visibilidade: 'publicado' })),
    excluirMaterial: vi.fn().mockResolvedValue({
      material_id: 'M1',
      removido: true,
      oci_removido: true,
    }),
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

describe('MateriaisView', () => {
  it('lista os materiais com as ações do catálogo', async () => {
    renderComApi(<MateriaisView />);

    expect(await screen.findByText('Dominando Redes na Nuvem')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /abrir/i })).toHaveAttribute(
      'href',
      '/empresa/resultado/M1',
    );
    expect(screen.getByRole('button', { name: /editar/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /excluir/i })).toBeInTheDocument();
  });

  it('publica um rascunho', async () => {
    const atualizar = vi
      .fn()
      .mockResolvedValue({ ...material(), visibilidade: 'publicado' });
    renderComApi(<MateriaisView />, {
      listarMateriais: vi.fn().mockResolvedValue(pagina([material()])),
      atualizarMaterial: atualizar,
    });

    await userEvent.click(await screen.findByRole('button', { name: /publicar/i }));

    expect(atualizar).toHaveBeenCalledWith('M1', { visibilidade: 'publicado' });
    expect(await screen.findByRole('status')).toHaveTextContent('Material publicado.');
  });

  it('despublica um material publicado', async () => {
    const atualizar = vi.fn().mockResolvedValue(material({ visibilidade: 'rascunho' }));
    renderComApi(<MateriaisView />, {
      listarMateriais: vi
        .fn()
        .mockResolvedValue(pagina([material({ visibilidade: 'publicado' })])),
      atualizarMaterial: atualizar,
    });

    await userEvent.click(await screen.findByRole('button', { name: /despublicar/i }));

    expect(atualizar).toHaveBeenCalledWith('M1', { visibilidade: 'rascunho' });
    expect(await screen.findByRole('status')).toHaveTextContent('Material despublicado.');
  });

  it('faz a publicação otimista com rollback em erro', async () => {
    const atualizar = vi.fn().mockRejectedValue(new Error('falhou'));
    renderComApi(<MateriaisView />, { atualizarMaterial: atualizar });

    await userEvent.click(await screen.findByRole('button', { name: /publicar/i }));

    expect(await screen.findByRole('alert')).toBeInTheDocument();
    expect(await screen.findByRole('button', { name: /publicar/i })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /despublicar/i })).not.toBeInTheDocument();
  });

  it('edita o título pelo diálogo', async () => {
    const atualizar = vi
      .fn()
      .mockResolvedValue(material({ titulo: 'Título novo do material' }));
    renderComApi(<MateriaisView />, { atualizarMaterial: atualizar });

    await userEvent.click(await screen.findByRole('button', { name: /editar/i }));
    const dialogo = await screen.findByRole('dialog');
    const campo = within(dialogo).getByLabelText(/título do material/i);
    await userEvent.clear(campo);
    await userEvent.type(campo, 'Título novo do material');
    await userEvent.click(within(dialogo).getByRole('button', { name: /salvar/i }));

    await waitFor(() =>
      expect(atualizar).toHaveBeenCalledWith('M1', { titulo: 'Título novo do material' }),
    );
    expect(await screen.findByRole('status')).toHaveTextContent('Material atualizado.');
  });

  it('devolve o erro 422 do título para o campo', async () => {
    const { ErroApi } = await import('@/services/api/erros');
    const atualizar = vi.fn().mockRejectedValue(
      new ErroApi(
        {
          erro: {
            codigo: 'VALIDACAO',
            mensagem: 'Dados inválidos',
            campos: { titulo: 'Deve ter entre 3 e 150 caracteres.' },
          },
        },
        422,
      ),
    );
    renderComApi(<MateriaisView />, { atualizarMaterial: atualizar });

    await userEvent.click(await screen.findByRole('button', { name: /editar/i }));
    const dialogo = await screen.findByRole('dialog');
    const campo = within(dialogo).getByLabelText(/título do material/i);
    await userEvent.clear(campo);
    await userEvent.type(campo, 'Título válido');
    await userEvent.click(within(dialogo).getByRole('button', { name: /salvar/i }));

    expect(await screen.findByText('Deve ter entre 3 e 150 caracteres.')).toBeInTheDocument();
    expect(campo).toHaveAttribute('aria-invalid', 'true');
  });

  it('exclui com confirmação e mostra aviso de OCI', async () => {
    const excluir = vi.fn().mockResolvedValue({
      material_id: 'M1',
      removido: true,
      oci_removido: false,
      aviso: 'Objeto OCI indisponível; a remoção local foi concluída.',
    });
    renderComApi(<MateriaisView />, { excluirMaterial: excluir });

    await userEvent.click(await screen.findByRole('button', { name: /excluir/i }));
    const dialogo = await screen.findByRole('dialog');
    expect(within(dialogo).getByText(/Dominando Redes na Nuvem/)).toBeInTheDocument();
    await userEvent.click(within(dialogo).getByRole('button', { name: /confirmar e excluir/i }));

    await waitFor(() => expect(excluir).toHaveBeenCalledWith('M1'));
    const toast = await screen.findByRole('status');
    expect(toast).toHaveTextContent('Material excluído.');
    expect(toast).toHaveTextContent('Objeto OCI indisponível; a remoção local foi concluída.');
  });

  it('filtra pela visibilidade refletindo na URL', async () => {
    renderComApi(<MateriaisView />);

    await screen.findByText('Dominando Redes na Nuvem');
    await userEvent.selectOptions(
      screen.getByLabelText(/todas as visibilidades/i),
      'publicado',
    );

    expect(mocks.replace).toHaveBeenCalledWith('/empresa/materiais?visibilidade=publicado');
  });

  it('mostra vazio com CTA para gerar material', async () => {
    renderComApi(<MateriaisView />, {
      listarMateriais: vi.fn().mockResolvedValue(pagina([])),
    });

    expect(await screen.findByText(/nenhum material gerado ainda/i)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /gerar material/i })).toHaveAttribute(
      'href',
      '/empresa/gerar',
    );
  });

  it('mostra erro com retry', async () => {
    renderComApi(<MateriaisView />, {
      listarMateriais: vi.fn().mockRejectedValue(new Error('falhou')),
    });

    expect(await screen.findByRole('alert')).toHaveTextContent('inesperado');
    expect(screen.getByRole('button', { name: /tentar novamente/i })).toBeInTheDocument();
  });

  it('pagina pela URL', async () => {
    renderComApi(<MateriaisView />, {
      listarMateriais: vi.fn().mockResolvedValue({
        itens: [material()],
        pagina: 1,
        tamanho_pagina: 12,
        total: 14,
        total_paginas: 2,
      }),
    });

    await screen.findByText('Dominando Redes na Nuvem');
    await userEvent.click(screen.getByRole('button', { name: /próxima/i }));

    expect(mocks.replace).toHaveBeenCalledWith('/empresa/materiais?pagina=2');
  });

  it('mostra paginação quando a página está fora do intervalo', async () => {
    mocks.params = new URLSearchParams('pagina=99');
    renderComApi(<MateriaisView />, {
      listarMateriais: vi.fn().mockResolvedValue({
        itens: [],
        pagina: 99,
        tamanho_pagina: 12,
        total: 40,
        total_paginas: 4,
      }),
    });

    expect(await screen.findByText('Página 99 de 4')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /anterior/i })).toBeEnabled();
    expect(screen.getByRole('button', { name: /próxima/i })).toBeDisabled();
    expect(screen.queryByText(/nenhum material gerado ainda/i)).not.toBeInTheDocument();
  });
});
