// @vitest-environment node
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it } from 'vitest';
import { server } from '../server';
import {
  limparEstadoCatalogo,
  semearAlunosMock,
  semearMateriaisMock,
} from '../estadoCatalogo';
import { MODELOS_CHAT_MOCK } from './chat';
import { httpApiClient } from '@/services/api/httpApiClient';
import { ErroApi } from '@/services/api/erros';

const ANA = '01JALUNO000000000000000001';
const INATIVO = '01JALUNO000000000000000006';
const CARDS = '01JAVCNFLCARD00000000001';
const QUIZ = '01JAVCNQUIZ000000000002';

// Mesmo arranjo do teste de handlers do aluno: o MSW troca o fetch global e o
// shim de caminho relativo precisa ser reaplicado depois do listen.
let fetchAnterior: typeof fetch;

beforeAll(() => {
  fetchAnterior = globalThis.fetch;
  server.listen({ onUnhandledFrame: 'error' });
  const fetchInterceptado = globalThis.fetch;
  globalThis.fetch = ((entradaFetch: RequestInfo | URL, init?: RequestInit) => {
    const url =
      typeof entradaFetch === 'string' && entradaFetch.startsWith('/')
        ? `http://localhost${entradaFetch}`
        : entradaFetch;
    return fetchInterceptado(url as RequestInfo, init);
  }) as typeof fetch;
});

beforeEach(() => {
  semearAlunosMock();
  semearMateriaisMock();
});

afterEach(() => {
  server.resetHandlers();
  limparEstadoCatalogo();
});


beforeEach(() => {
  semearAlunosMock();
  semearMateriaisMock();
});

afterEach(() => {
  server.resetHandlers();
  limparEstadoCatalogo();
});

afterAll(() => {
  server.close();
  globalThis.fetch = fetchAnterior;
});

describe('mocks do chat', () => {
  it('lista os modelos com o padrão', async () => {
    await expect(httpApiClient.listarModelosChat()).resolves.toEqual(MODELOS_CHAT_MOCK);
  });

  it('responde ao aluno com citação do material', async () => {
    const saida = await httpApiClient.perguntarAluno(ANA, QUIZ, {
      pergunta: 'Para que serve o NAT Gateway?',
    });

    expect(saida.recusou).toBe(false);
    expect(saida.fundamentada).toBe(true);
    expect(saida.citacoes[0]).toMatchObject({ id: 'P1', origem: 'pacote' });
    expect(saida.resposta).toContain('[P1]');
  });

  it('recusa quando a pergunta não tem relação com o material', async () => {
    const saida = await httpApiClient.perguntarAluno(ANA, QUIZ, {
      pergunta: 'Quem descobriu o Brasil?',
    });

    expect(saida).toMatchObject({ recusou: true, fundamentada: false, citacoes: [] });
    expect(saida.resposta).toBe('Não encontrei isso no material.');
  });

  it('não responde ao aluno sobre material em rascunho', async () => {
    const erro = await httpApiClient
      .perguntarAluno(ANA, CARDS, { pergunta: 'O que é uma VCN?' })
      .catch((e) => e);

    expect(erro.status).toBe(404);
    expect(erro.problema.erro.codigo).toBe('MATERIAL_NAO_DISPONIVEL');
  });

  it('usa o modelo pedido e rejeita um fora da lista', async () => {
    const ok = await httpApiClient.perguntarEmpresa(CARDS, {
      pergunta: 'O que é uma VCN?',
      modelo: MODELOS_CHAT_MOCK.modelos[1],
    });
    expect(ok.modelo).toBe(MODELOS_CHAT_MOCK.modelos[1]);

    const erro = await httpApiClient
      .perguntarEmpresa(CARDS, { pergunta: 'O que é uma VCN?', modelo: 'x/y' })
      .catch((e) => e);
    expect(erro).toBeInstanceOf(ErroApi);
    expect(erro.problema.erro.codigo).toBe('CHAT_MODELO_NAO_PERMITIDO');
    expect(erro.problema.erro.detalhes).toEqual({ modelos_permitidos: MODELOS_CHAT_MOCK.modelos });
  });

  it('valida pergunta vazia e longa com o campo da pergunta', async () => {
    const vazia = await httpApiClient.perguntarEmpresa(CARDS, { pergunta: '   ' }).catch((e) => e);
    expect(vazia.problema.erro).toMatchObject({
      codigo: 'PERGUNTA_VAZIA',
      campos: { pergunta: expect.any(String) },
    });
    expect(vazia.status).toBe(422);

    const longa = await httpApiClient
      .perguntarEmpresa(CARDS, { pergunta: 'a'.repeat(1001) })
      .catch((e) => e);
    expect(longa.problema.erro.codigo).toBe('PERGUNTA_LONGA');
  });

  it('respeita o vínculo e o status do aluno e a existência do material', async () => {
    const inativo = await httpApiClient
      .perguntarAluno(INATIVO, QUIZ, { pergunta: 'Qualquer coisa' })
      .catch((e) => e);
    expect(inativo.status).toBe(403);
    expect(inativo.problema.erro.codigo).toBe('ALUNO_INATIVO');

    const sumido = await httpApiClient
      .perguntarEmpresa('NAO_EXISTE', { pergunta: 'Qualquer coisa' })
      .catch((e) => e);
    expect(sumido.status).toBe(404);
    expect(sumido.problema.erro.codigo).toBe('MATERIAL_NAO_ENCONTRADO');
  });
});
