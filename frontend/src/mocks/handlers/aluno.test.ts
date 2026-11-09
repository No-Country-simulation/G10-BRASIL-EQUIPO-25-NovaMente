// @vitest-environment node
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it } from 'vitest';
import { server } from '../server';
import {
  limparEstadoCatalogo,
  semearAlunosMock,
  semearMateriaisMock,
} from '../estadoCatalogo';
import { httpApiClient } from '@/services/api/httpApiClient';
import { ErroApi } from '@/services/api/erros';

const ANA = '01JALUNO000000000000000001';
const BRUNO = '01JALUNO000000000000000002';
const INATIVO = '01JALUNO000000000000000006';
const QUIZ = '01JAVCNQUIZ000000000002';
const CARDS = '01JAVCNFLCARD00000000001';

// O MSW substitui o fetch global no listen e, em ambiente node, o shim relativo
// do setup deixa de valer; reencapsulamos depois do listen para o cliente
// continuar chamando caminhos relativos.
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

afterAll(() => {
  server.close();
  globalThis.fetch = fetchAnterior;
});

describe('handlers da área do aluno', () => {
  it('lista a identificação somente de ativos e sem e-mail', async () => {
    const itens = await httpApiClient.listarIdentificacaoAluno();

    expect(itens).toHaveLength(5);
    expect(itens.map((item) => item.nome)).toEqual([
      'Ana Beatriz Silva',
      'Bruno Carvalho',
      'Carla Mendes',
      'Diego Ferreira',
      'Elisa Rocha',
    ]);
    expect(itens[0]).toEqual({ aluno_id: ANA, nome: 'Ana Beatriz Silva' });
    expect(itens.every((item) => !('email' in item))).toBe(true);
  });

  it('mostra no catálogo apenas publicados e vinculados', async () => {
    const pagina = await httpApiClient.listarCatalogoAluno(ANA);

    expect(pagina.total).toBe(2);
    expect(pagina.itens.map((item) => item.material_id)).toEqual([
      '01JAVCNRESU000000000004',
      QUIZ,
    ]);
    expect(pagina.itens[0].conceitos_chave.length).toBeGreaterThan(0);
  });

  it('filtra por q, formato, perfil e ordena', async () => {
    const porFormato = await httpApiClient.listarCatalogoAluno(ANA, { formato: 'Quiz' });
    expect(porFormato.itens.map((item) => item.material_id)).toEqual([QUIZ]);

    const porQ = await httpApiClient.listarCatalogoAluno(ANA, { q: 'roteamento' });
    expect(porQ.itens.map((item) => item.material_id)).toEqual([QUIZ]);

    const porPerfil = await httpApiClient.listarCatalogoAluno(ANA, { perfil: 'Gestor' });
    expect(porPerfil.itens.map((item) => item.material_id)).toEqual([
      '01JAVCNRESU000000000004',
    ]);

    const porTitulo = await httpApiClient.listarCatalogoAluno(ANA, { ordenar: 'titulo:asc' });
    const titulos = porTitulo.itens.map((item) => item.titulo);
    expect(titulos).toEqual([...titulos].sort((a, b) => a.localeCompare(b, 'pt-BR')));
  });

  it('responde 403 para aluno inativo e 404 para aluno inexistente', async () => {
    const inativo = await httpApiClient.listarCatalogoAluno(INATIVO).catch((e: unknown) => e);
    expect(inativo).toBeInstanceOf(ErroApi);
    expect(inativo).toMatchObject({
      status: 403,
      problema: { erro: { codigo: 'ALUNO_INATIVO' } },
    });

    const inexistente = await httpApiClient
      .listarCatalogoAluno('NAO_EXISTE')
      .catch((e: unknown) => e);
    expect(inexistente).toMatchObject({
      status: 404,
      problema: { erro: { codigo: 'ALUNO_NAO_ENCONTRADO' } },
    });
  });

  it('responde 422 sem aluno_id ou com filtros inválidos', async () => {
    const semAluno = await httpApiClient
      .listarCatalogoAluno('')
      .catch((e: unknown) => e);
    expect(semAluno).toMatchObject({
      status: 422,
      problema: { erro: { codigo: 'VALIDACAO', campos: { aluno_id: 'Informe o aluno.' } } },
    });

    const filtroInvalido = await httpApiClient
      .listarCatalogoAluno(ANA, { formato: 'Inexistente' as never })
      .catch((e: unknown) => e);
    expect(filtroInvalido).toMatchObject({
      status: 422,
      problema: { erro: { codigo: 'VALIDACAO', campos: { formato: 'Formato de saída desconhecido.' } } },
    });
  });

  it('entrega o detalhe apenas de material publicado e vinculado', async () => {
    const detalhe = await httpApiClient.obterMaterialAluno(ANA, QUIZ);
    expect(detalhe.material.material_id).toBe(QUIZ);
    expect(detalhe.pacote.adaptacao_id).toBe(QUIZ);

    const rascunho = await httpApiClient.obterMaterialAluno(ANA, CARDS).catch((e: unknown) => e);
    expect(rascunho).toMatchObject({
      status: 404,
      problema: { erro: { codigo: 'MATERIAL_NAO_DISPONIVEL' } },
    });

    const naoVinculado = await httpApiClient
      .obterMaterialAluno(BRUNO, QUIZ)
      .catch((e: unknown) => e);
    expect(naoVinculado).toMatchObject({
      status: 404,
      problema: { erro: { codigo: 'MATERIAL_NAO_DISPONIVEL' } },
    });
  });
});
