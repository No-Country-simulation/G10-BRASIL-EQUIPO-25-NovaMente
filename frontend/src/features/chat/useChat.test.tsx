import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, renderHook } from '@testing-library/react';
import type { ReactNode } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { montarHistorico, useChat } from './useChat';
import type { TurnoChat } from './useChat';
import { ApiProvider } from '@/services/api/ApiProvider';
import { ErroApi } from '@/services/api/erros';
import type { NovaMenteApi } from '@/services/api/NovaMenteApi';
import type { RespostaChat } from '@/types/novamente';

const resposta = (texto: string): RespostaChat => ({
  resposta: texto,
  citacoes: [],
  base: 'pacote',
  recusou: false,
  fundamentada: true,
  ancoragem: 0.9,
  modelo: 'google/gemma-4-31b-it',
  trechos_usados: 1,
});

function montar(api: Partial<NovaMenteApi>) {
  const cliente = api as unknown as NovaMenteApi;
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const wrapper = ({ children }: { children: ReactNode }) => (
    <ApiProvider client={cliente}>
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    </ApiProvider>
  );
  return wrapper;
}

const alvoAluno = { tipo: 'aluno', alunoId: 'A1', materialId: 'M1' } as const;

afterEach(() => vi.useRealTimers());

describe('montarHistorico', () => {
  it('mantém só as 10 últimas mensagens e corta o conteúdo em 2000', () => {
    const turnos: TurnoChat[] = Array.from({ length: 8 }, (_, i) => ({
      id: i,
      pergunta: `p${i}`,
      resposta: resposta(i === 7 ? 'x'.repeat(2500) : `r${i}`),
    }));

    const historico = montarHistorico(turnos);

    expect(historico).toHaveLength(10);
    expect(historico[0]).toEqual({ papel: 'user', conteudo: 'p3' });
    expect(historico[9].conteudo).toHaveLength(2000);
  });
});

describe('useChat', () => {
  it('envia como aluno e guarda o turno com o histórico dos anteriores', async () => {
    const perguntarAluno = vi
      .fn()
      .mockResolvedValueOnce(resposta('Primeira.'))
      .mockResolvedValueOnce(resposta('Segunda.'));
    const { result } = renderHook(() => useChat(alvoAluno), { wrapper: montar({ perguntarAluno }) });

    let ok = false;
    await act(async () => {
      ok = await result.current.enviar('  Primeira pergunta  ', 'google/gemma-4-31b-it');
    });
    await act(async () => {
      await result.current.enviar('Segunda pergunta');
    });

    expect(ok).toBe(true);
    expect(result.current.turnos.map((t) => t.pergunta)).toEqual([
      'Primeira pergunta',
      'Segunda pergunta',
    ]);
    expect(perguntarAluno.mock.calls[0]).toEqual([
      'A1',
      'M1',
      { pergunta: 'Primeira pergunta', historico: [], modelo: 'google/gemma-4-31b-it' },
    ]);
    expect(perguntarAluno.mock.calls[1][2]).toEqual({
      pergunta: 'Segunda pergunta',
      historico: [
        { papel: 'user', conteudo: 'Primeira pergunta' },
        { papel: 'assistant', conteudo: 'Primeira.' },
      ],
    });
  });

  it('usa a rota da empresa quando o alvo é a empresa', async () => {
    const perguntarEmpresa = vi.fn().mockResolvedValue(resposta('Ok.'));
    const { result } = renderHook(() => useChat({ tipo: 'empresa', materialId: 'M9' }), {
      wrapper: montar({ perguntarEmpresa }),
    });

    await act(async () => {
      await result.current.enviar('Pergunta');
    });

    expect(perguntarEmpresa).toHaveBeenCalledWith('M9', { pergunta: 'Pergunta', historico: [] });
  });

  it('ignora pergunta em branco sem chamar a API', async () => {
    const perguntarAluno = vi.fn();
    const { result } = renderHook(() => useChat(alvoAluno), { wrapper: montar({ perguntarAluno }) });

    let ok = true;
    await act(async () => {
      ok = await result.current.enviar('   ');
    });

    expect(ok).toBe(false);
    expect(perguntarAluno).not.toHaveBeenCalled();
  });

  it('na falha guarda o erro, não cria turno e conta a espera do Retry-After', async () => {
    vi.useFakeTimers();
    const falha = new ErroApi(
      { erro: { codigo: 'CHAT_LIMITE_EXCEDIDO', mensagem: 'Muitas perguntas.' } },
      429,
      3,
    );
    const perguntarAluno = vi.fn().mockRejectedValue(falha);
    const { result } = renderHook(() => useChat(alvoAluno), { wrapper: montar({ perguntarAluno }) });

    let ok = true;
    await act(async () => {
      ok = await result.current.enviar('Pergunta');
    });

    expect(ok).toBe(false);
    expect(result.current.erro).toBe(falha);
    expect(result.current.turnos).toHaveLength(0);
    expect(result.current.pendente).toBeNull();
    expect(result.current.espera).toBe(3);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(3000);
    });
    expect(result.current.espera).toBe(0);
  });

  it('rejeita resposta fora do contrato como erro', async () => {
    const perguntarAluno = vi.fn().mockResolvedValue({ resposta: '' });
    const { result } = renderHook(() => useChat(alvoAluno), { wrapper: montar({ perguntarAluno }) });

    await act(async () => {
      await result.current.enviar('Pergunta');
    });

    expect(result.current.erro).toBeInstanceOf(Error);
    expect(result.current.turnos).toHaveLength(0);
  });

  it('limpar zera conversa e erro', async () => {
    const perguntarAluno = vi.fn().mockResolvedValue(resposta('Ok.'));
    const { result } = renderHook(() => useChat(alvoAluno), { wrapper: montar({ perguntarAluno }) });

    await act(async () => {
      await result.current.enviar('Pergunta');
    });
    act(() => result.current.limpar());

    expect(result.current.turnos).toHaveLength(0);
    expect(result.current.erro).toBeNull();
  });

  it('descarta a resposta que chega depois de limpar a conversa', async () => {
    let liberar: (r: RespostaChat) => void = () => {};
    const perguntarAluno = vi.fn().mockReturnValue(
      new Promise<RespostaChat>((resolve) => {
        liberar = resolve;
      }),
    );
    const { result } = renderHook(() => useChat(alvoAluno), { wrapper: montar({ perguntarAluno }) });

    let envio: Promise<boolean> = Promise.resolve(false);
    act(() => {
      envio = result.current.enviar('Pergunta');
    });
    act(() => result.current.limpar());
    await act(async () => {
      liberar(resposta('Atrasada.'));
      await envio;
    });

    expect(result.current.turnos).toHaveLength(0);
  });
});
