// @vitest-environment node
import { afterEach, describe, expect, it, vi } from 'vitest';
import { httpApiClient } from './httpApiClient';
import { ErroApi, ErroContrato, lerRetryAfter } from './erros';

function json(corpo: unknown, status = 200, headers: Record<string, string> = {}): Response {
  return new Response(JSON.stringify(corpo), {
    status,
    headers: { 'Content-Type': 'application/json', ...headers },
  });
}

const resposta = {
  resposta: 'Uma VCN é uma rede virtual privada. [P1]',
  citacoes: [{ id: 'P1', origem: 'pacote', excerto: 'VCN é uma rede virtual privada.' }],
  base: 'pacote',
  recusou: false,
  fundamentada: true,
  ancoragem: 0.9,
  modelo: 'google/gemma-4-31b-it',
  trechos_usados: 1,
};

afterEach(() => vi.unstubAllGlobals());

describe('httpApiClient — chat', () => {
  it('lista os modelos permitidos', async () => {
    const fetchMock = vi.fn().mockResolvedValue(json({ padrao: 'a/b', modelos: ['a/b', 'c/d'] }));
    vi.stubGlobal('fetch', fetchMock);

    await expect(httpApiClient.listarModelosChat()).resolves.toEqual({
      padrao: 'a/b',
      modelos: ['a/b', 'c/d'],
    });
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/chat/modelos', undefined);
  });

  it('pergunta como aluno com aluno_id na query e corpo JSON', async () => {
    const fetchMock = vi.fn().mockResolvedValue(json(resposta));
    vi.stubGlobal('fetch', fetchMock);

    const saida = await httpApiClient.perguntarAluno('A 1', 'M/1', {
      pergunta: 'O que é VCN?',
      historico: [],
      modelo: 'google/gemma-4-31b-it',
    });

    expect(saida.citacoes[0].id).toBe('P1');
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe('/api/v1/aluno/materiais/M%2F1/chat?aluno_id=A+1');
    expect(init.method).toBe('POST');
    expect(JSON.parse(String(init.body))).toEqual({
      pergunta: 'O que é VCN?',
      historico: [],
      modelo: 'google/gemma-4-31b-it',
    });
  });

  it('pergunta como empresa sem aluno_id', async () => {
    const fetchMock = vi.fn().mockResolvedValue(json(resposta));
    vi.stubGlobal('fetch', fetchMock);

    await httpApiClient.perguntarEmpresa('M1', { pergunta: 'O que é VCN?' });

    expect(fetchMock.mock.calls[0][0]).toBe('/api/v1/materiais/M1/chat');
  });

  it('rejeita resposta fora do contrato', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(json({ ...resposta, ancoragem: 3 })));

    await expect(httpApiClient.perguntarEmpresa('M1', { pergunta: 'x' })).rejects.toBeInstanceOf(
      ErroContrato,
    );
  });

  it('mantém o código do erro e o Retry-After do 429', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        json(
          { erro: { codigo: 'CHAT_LIMITE_EXCEDIDO', mensagem: 'Muitas perguntas.' } },
          429,
          { 'Retry-After': '12' },
        ),
      ),
    );

    const erro = await httpApiClient.perguntarEmpresa('M1', { pergunta: 'x' }).catch((e) => e);

    expect(erro).toBeInstanceOf(ErroApi);
    expect(erro).toMatchObject({ status: 429, retryAfter: 12 });
    expect(erro.problema.erro.codigo).toBe('CHAT_LIMITE_EXCEDIDO');
  });

  it('aceita o campo extra `detalhes` no erro de modelo não permitido', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        json(
          {
            erro: {
              codigo: 'CHAT_MODELO_NAO_PERMITIDO',
              mensagem: 'Modelo não permitido.',
              detalhes: { modelos_permitidos: ['a/b'] },
            },
          },
          422,
        ),
      ),
    );

    const erro = await httpApiClient
      .perguntarEmpresa('M1', { pergunta: 'x', modelo: 'z/z' })
      .catch((e) => e);

    expect(erro.problema.erro.codigo).toBe('CHAT_MODELO_NAO_PERMITIDO');
    expect(erro.problema.erro.detalhes).toEqual({ modelos_permitidos: ['a/b'] });
  });

  it('reconhece os códigos NAO_AUTORIZADO e GERACAO_OCUPADA', async () => {
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValueOnce(json({ erro: { codigo: 'NAO_AUTORIZADO', mensagem: 'Negado.' } }, 401))
        .mockResolvedValueOnce(
          json({ erro: { codigo: 'GERACAO_OCUPADA', mensagem: 'Ocupado.' } }, 503, {
            'Retry-After': '30',
          }),
        ),
    );

    const negado = await httpApiClient.listarModelosChat().catch((e) => e);
    const ocupado = await httpApiClient.listarModelosChat().catch((e) => e);

    expect(negado.problema.erro.codigo).toBe('NAO_AUTORIZADO');
    expect(ocupado.problema.erro.codigo).toBe('GERACAO_OCUPADA');
    expect(ocupado.retryAfter).toBe(30);
  });
});

describe('lerRetryAfter', () => {
  const com = (valor?: string) =>
    new Response('', { headers: valor === undefined ? {} : { 'Retry-After': valor } });

  it('lê segundos inteiros positivos', () => {
    expect(lerRetryAfter(com('10'))).toBe(10);
  });

  it('ignora ausência, zero, data HTTP e lixo', () => {
    expect(lerRetryAfter(com())).toBeUndefined();
    expect(lerRetryAfter(com('0'))).toBeUndefined();
    expect(lerRetryAfter(com('Wed, 21 Oct 2026 07:28:00 GMT'))).toBeUndefined();
    expect(lerRetryAfter(com('-3'))).toBeUndefined();
  });
});
