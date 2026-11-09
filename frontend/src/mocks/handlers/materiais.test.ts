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

describe('handlers de materiais', () => {
  it('lista com filtros e ordenação', async () => {
    const publicados = await httpApiClient.listarMateriais({ visibilidade: 'publicado' });
    expect(publicados.total).toBe(2);

    const porTitulo = await httpApiClient.listarMateriais({ ordenar: 'titulo:asc' });
    const titulos = porTitulo.itens.map((material) => material.titulo);
    expect(titulos).toEqual([...titulos].sort((a, b) => a.localeCompare(b, 'pt-BR')));

    const busca = await httpApiClient.listarMateriais({ q: 'roteamento' });
    expect(busca.itens.map((material) => material.formato)).toEqual(['Quiz']);
  });

  it('responde 422 para filtros inválidos', async () => {
    const erro = await httpApiClient
      .listarMateriais({ visibilidade: 'invalida' as never })
      .catch((e: unknown) => e);

    expect(erro).toBeInstanceOf(ErroApi);
    expect(erro).toMatchObject({
      status: 422,
      problema: { erro: { codigo: 'VALIDACAO', campos: { visibilidade: 'Visibilidade desconhecida.' } } },
    });
  });

  it('obtém o detalhe com o pacote e responde 404 para id inexistente', async () => {
    const detalhe = await httpApiClient.obterMaterial(CARDS);

    expect(detalhe.material.material_id).toBe(CARDS);
    expect(detalhe.pacote.adaptacao_id).toBe(CARDS);

    const erro = await httpApiClient.obterMaterial('NAO_EXISTE').catch((e: unknown) => e);
    expect(erro).toMatchObject({
      status: 404,
      problema: { erro: { codigo: 'MATERIAL_NAO_ENCONTRADO' } },
    });
  });

  it('atualiza título/visibilidade e responde 422 para corpo inválido', async () => {
    const atualizado = await httpApiClient.atualizarMaterial(CARDS, {
      titulo: '  Título novo  ',
      visibilidade: 'publicado',
    });
    expect(atualizado).toMatchObject({ titulo: 'Título novo', visibilidade: 'publicado' });

    const vazio = await httpApiClient
      .atualizarMaterial(CARDS, {})
      .catch((e: unknown) => e);
    expect(vazio).toMatchObject({ status: 422, problema: { erro: { codigo: 'VALIDACAO' } } });

    const extra = await httpApiClient
      .atualizarMaterial(CARDS, { formato: 'Quiz' } as never)
      .catch((e: unknown) => e);
    expect(extra).toMatchObject({ status: 422, problema: { erro: { codigo: 'VALIDACAO' } } });

    const inexistente = await httpApiClient
      .atualizarMaterial('NAO_EXISTE', { titulo: 'Título novo' })
      .catch((e: unknown) => e);
    expect(inexistente).toMatchObject({
      status: 404,
      problema: { erro: { codigo: 'MATERIAL_NAO_ENCONTRADO' } },
    });
  });

  it('exclui o material e devolve o resultado da remoção no OCI', async () => {
    const remocao = await httpApiClient.excluirMaterial(CARDS);

    expect(remocao).toMatchObject({ material_id: CARDS, removido: true, oci_removido: true });
    await expect(httpApiClient.obterMaterial(CARDS)).rejects.toMatchObject({ status: 404 });
  });
});
