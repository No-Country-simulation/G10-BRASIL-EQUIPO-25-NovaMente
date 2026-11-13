import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { VinculosPanel } from './VinculosPanel';
import { ErroAplicarVinculos } from '@/features/alunos/useVinculos';
import { ApiProvider } from '@/services/api/ApiProvider';
import type { NovaMenteApi } from '@/services/api/NovaMenteApi';
import type {
  MaterialResumo,
  PaginaMateriais,
  VinculoMaterial,
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

const material = (over: Partial<MaterialResumo> = {}): MaterialResumo => {
  const base: MaterialResumo = {
    material_id: 'M1',
    adaptacao_id: 'M1',
    titulo: 'Material M1',
    documento_titulo: 'Documento M1',
    perfil: 'Iniciante',
    formato: 'Flashcards',
    nivel: 'Didatico',
    nicho: 'Geral',
    visibilidade: 'publicado',
    tempo_estimado_estudo_minutos: 10,
    ancoragem_fonte_score: 0.9,
    status_upload: 'concluido',
    criado_em: '2026-10-01T09:00:00Z',
    atualizado_em: '2026-10-01T09:00:00Z',
    ...over,
  };
  return {
    ...base,
    titulo: over.titulo ?? `Material ${base.material_id}`,
    documento_titulo: over.documento_titulo ?? `Documento ${base.material_id}`,
  };
};

const pagina = (itens: MaterialResumo[] = [material()]): PaginaMateriais => ({
  itens,
  pagina: 1,
  tamanho_pagina: 12,
  total: itens.length,
  total_paginas: itens.length > 0 ? 1 : 0,
});

const vinculo = (materialId: string): VinculoMaterial => ({
  material_id: materialId,
  titulo: `Material ${materialId}`,
  formato: 'Flashcards',
  perfil: 'Iniciante',
  visibilidade: 'publicado',
  vinculado_em: '2026-10-01T09:00:00Z',
});

function renderComApi(ui: ReactNode, api: Partial<NovaMenteApi> = {}) {
  const cliente = {
    listarMateriais: vi.fn().mockResolvedValue(pagina()),
    listarVinculos: vi.fn().mockResolvedValue({ aluno_id: 'A1', itens: [vinculo('M1')] }),
    adicionarVinculo: vi.fn().mockResolvedValue(vinculo('M1')),
    removerVinculo: vi.fn().mockResolvedValue(undefined),
    ...api,
  } as unknown as NovaMenteApi;
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <ApiProvider client={cliente}>
      <QueryClientProvider client={client}>{ui}</QueryClientProvider>
    </ApiProvider>,
  );
  return { api: cliente };
}

beforeEach(() => {
  mocks.replace.mockReset();
  mocks.push.mockReset();
  mocks.params = new URLSearchParams();
});

describe('VinculosPanel', () => {
  it('não desvincula material escondido pelo filtro', async () => {
    const aplicar = vi.fn().mockResolvedValue(undefined);
    renderComApi(<VinculosPanel alunoId="A1" aplicar={aplicar} />, {
      listarMateriais: vi.fn().mockResolvedValue(pagina([material({ material_id: 'M2' })])),
      listarVinculos: vi.fn().mockResolvedValue({
        aluno_id: 'A1',
        itens: [vinculo('M1'), vinculo('M2')],
      }),
    });

    await screen.findByText('Material M2');
    await userEvent.click(screen.getByRole('checkbox', { name: /material m2/i }));
    await userEvent.click(screen.getByRole('button', { name: /salvar vínculos/i }));

    expect(aplicar).toHaveBeenCalledWith({ adicionar: [], remover: ['M2'] });
    expect(aplicar).not.toHaveBeenCalledWith(expect.objectContaining({ remover: ['M1'] }));
  });

  it('adiciona material não vinculado pela diferença', async () => {
    const aplicar = vi.fn().mockResolvedValue(undefined);
    renderComApi(<VinculosPanel alunoId="A1" aplicar={aplicar} />, {
      listarMateriais: vi.fn().mockResolvedValue(pagina([material({ material_id: 'M1' })])),
      listarVinculos: vi.fn().mockResolvedValue({ aluno_id: 'A1', itens: [] }),
    });

    await screen.findByText('Material M1');
    await userEvent.click(screen.getByRole('checkbox', { name: /material m1/i }));
    await userEvent.click(screen.getByRole('button', { name: /salvar vínculos/i }));

    expect(aplicar).toHaveBeenCalledWith({ adicionar: ['M1'], remover: [] });
  });

  it('mostra falha parcial com os títulos e refaz as consultas', async () => {
    const aplicar = vi
      .fn()
      .mockRejectedValue(
        new ErroAplicarVinculos([{ materialId: 'M1', operacao: 'remover' }]),
      );
    const { api } = renderComApi(<VinculosPanel alunoId="A1" aplicar={aplicar} />, {
      listarMateriais: vi.fn().mockResolvedValue(pagina([material({ material_id: 'M1' })])),
      listarVinculos: vi.fn().mockResolvedValue({
        aluno_id: 'A1',
        itens: [vinculo('M1')],
      }),
    });

    await screen.findByText('Material M1');
    await userEvent.click(screen.getByRole('checkbox', { name: /material m1/i }));
    await userEvent.click(screen.getByRole('button', { name: /salvar vínculos/i }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Material M1');
    await waitFor(() => expect(api.listarMateriais).toHaveBeenCalledTimes(2));
    await waitFor(() => expect(api.listarVinculos).toHaveBeenCalledTimes(2));
  });

  it('busca materiais pelo título sem sair da rota do aluno', async () => {
    const listarMateriais = vi.fn().mockResolvedValue(pagina([material()]));
    renderComApi(<VinculosPanel alunoId="A1" />, { listarMateriais });

    await screen.findByText('Material M1');
    await userEvent.type(screen.getByLabelText(/buscar material/i), 'vcn');

    await waitFor(() =>
      expect(listarMateriais).toHaveBeenCalledWith(expect.objectContaining({ q: 'vcn', pagina: 1 })),
    );
    expect(mocks.replace).not.toHaveBeenCalled();
  });

  it('mostra vazio com link para gerar material', async () => {
    renderComApi(<VinculosPanel alunoId="A1" />, {
      listarMateriais: vi.fn().mockResolvedValue(pagina([])),
      listarVinculos: vi.fn().mockResolvedValue({ aluno_id: 'A1', itens: [] }),
    });

    expect(await screen.findByText(/nenhum material cadastrado/i)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /gerar material/i })).toHaveAttribute(
      'href',
      '/empresa/gerar',
    );
  });
});
