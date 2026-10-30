import { renderHook } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { useExport } from './useExport';
import { ApiProvider } from '@/services/api/ApiProvider';
import type { NovaMenteApi } from '@/services/api/NovaMenteApi';
import type { AdaptacaoPacote } from '@/types/novamente';

const pacote = {
  adaptacao_id: '01JAVCNFLCARD00000000001',
  documento: { titulo: 'Introdução à VCN', origem: 'texto' },
  metadados: { perfil_aplicado: 'Iniciante', formato_gerado: 'Flashcards' },
} as unknown as AdaptacaoPacote;

function montar(conteudo: AdaptacaoPacote['conteudo_adaptado']) {
  const api = {
    exportar: vi.fn().mockResolvedValue(new Blob(['# md'])),
    baixarJson: vi.fn().mockResolvedValue(new Blob(['{}'])),
  } as unknown as NovaMenteApi;
  const wrapper = ({ children }: { children: React.ReactNode }) => <ApiProvider client={api}>{children}</ApiProvider>;
  const completo = { ...pacote, conteudo_adaptado: conteudo } as unknown as AdaptacaoPacote;
  return { api, wrapper, completo };
}

describe('useExport', () => {
  it('exporta markdown com o nome de arquivo derivado do pacote', async () => {
    URL.createObjectURL = vi.fn(() => 'blob:mock');
    URL.revokeObjectURL = vi.fn();
    let nomeBaixado: string | null = null;
    const clique = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {
      nomeBaixado = document.querySelector<HTMLAnchorElement>('a[download]')?.getAttribute('download') ?? null;
    });
    const { api, wrapper, completo } = montar({
      tipo: 'flashcards',
      titulo: 'Deck',
      introducao_contextualizada: 'Intro',
      itens: [
        { frente: 'a', verso: 'b' },
        { frente: 'c', verso: 'd' },
        { frente: 'e', verso: 'f' },
      ],
    });

    const { result } = renderHook(() => useExport(completo), { wrapper });
    await result.current.exportar('md');

    expect(api.exportar).toHaveBeenCalledWith('01JAVCNFLCARD00000000001', 'md');
    expect(clique).toHaveBeenCalledTimes(1);
    expect(nomeBaixado).toBe('novamente-introducao-a-vcn-iniciante-flashcards-01javcnf.md');
  });

  it('habilita CSV apenas para flashcards', () => {
    URL.createObjectURL = vi.fn(() => 'blob:mock');
    URL.revokeObjectURL = vi.fn();
    const flashcards = montar({
      tipo: 'flashcards',
      titulo: 'Deck',
      introducao_contextualizada: 'Intro',
      itens: [
        { frente: 'a', verso: 'b' },
        { frente: 'c', verso: 'd' },
        { frente: 'e', verso: 'f' },
      ],
    });
    const tutorial = montar({
      tipo: 'markdown',
      titulo: 'Tutorial',
      introducao_contextualizada: 'Intro',
      itens: '## Passo 1\n\nConteúdo longo o suficiente para o schema aceitar o material.',
    });

    const a = renderHook(() => useExport(flashcards.completo), { wrapper: flashcards.wrapper });
    const b = renderHook(() => useExport(tutorial.completo), { wrapper: tutorial.wrapper });
    expect(a.result.current.csvDisponivel).toBe(true);
    expect(b.result.current.csvDisponivel).toBe(false);
  });
});
