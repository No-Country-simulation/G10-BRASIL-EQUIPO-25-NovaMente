// @vitest-environment node
import { afterEach, describe, expect, it, vi } from 'vitest';
import { httpApiClient } from './httpApiClient';
import { ErroApi } from './erros';
import flashcardsFixture from '@/mocks/fixtures/flashcards-vcn-iniciante.json';

const ISO = '2026-10-21T14:02:11Z';

function materialResumo(extra: Record<string, unknown> = {}) {
  return {
    material_id: 'M1',
    adaptacao_id: '01JAVCNFLCARD00000000001',
    titulo: 'Dominando Redes na Nuvem (VCN) do Zero',
    documento_titulo: 'Introdução à Arquitetura de Redes VCN na OCI',
    perfil: 'Iniciante',
    formato: 'Flashcards',
    nivel: 'Didatico',
    nicho: 'Geral',
    visibilidade: 'rascunho',
    tempo_estimado_estudo_minutos: 5,
    ancoragem_fonte_score: 0.98,
    status_upload: 'concluido',
    criado_em: ISO,
    atualizado_em: ISO,
    ...extra,
  };
}

// Resposta mínima: o cliente só usa `ok`, `status` e `json()`.
function json(corpo: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => corpo,
  } as unknown as Response;
}

afterEach(() => vi.unstubAllGlobals());

describe('httpApiClient — materiais', () => {
  it('lista materiais com paginação, filtros e ordenação', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      json({
        itens: [materialResumo({ visibilidade: 'publicado' })],
        pagina: 2,
        tamanho_pagina: 5,
        total: 6,
        total_paginas: 2,
      }),
    );
    vi.stubGlobal('fetch', fetchMock);

    const pagina = await httpApiClient.listarMateriais({
      pagina: 2,
      tamanho_pagina: 5,
      q: 'vcn',
      formato: 'Flashcards',
      perfil: 'Iniciante',
      visibilidade: 'publicado',
      ordenar: 'titulo:asc',
    });

    expect(pagina.total).toBe(6);
    expect(pagina.itens[0].visibilidade).toBe('publicado');
    const url = String(fetchMock.mock.calls[0][0]);
    expect(url.startsWith('/api/v1/materiais?')).toBe(true);
    expect(url).toContain('pagina=2');
    expect(url).toContain('tamanho_pagina=5');
    expect(url).toContain('q=vcn');
    expect(url).toContain('formato=Flashcards');
    expect(url).toContain('perfil=Iniciante');
    expect(url).toContain('visibilidade=publicado');
    expect(url).toContain('ordenar=titulo%3Aasc');
  });

  it('valida MaterialDetalhe com pacote', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(json({ material: materialResumo(), pacote: flashcardsFixture })),
    );

    const detalhe = await httpApiClient.obterMaterial('M1');

    expect(detalhe.material.visibilidade).toBe('rascunho');
    expect(detalhe.pacote.adaptacao_id).toBe(flashcardsFixture.adaptacao_id);
  });

  it('atualiza material via PATCH e devolve o resumo', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      json(materialResumo({ titulo: 'Novo título', visibilidade: 'publicado' })),
    );
    vi.stubGlobal('fetch', fetchMock);

    const atualizado = await httpApiClient.atualizarMaterial('M1', {
      titulo: 'Novo título',
      visibilidade: 'publicado',
    });

    expect(atualizado).toMatchObject({ titulo: 'Novo título', visibilidade: 'publicado' });
    expect(fetchMock.mock.calls[0][0]).toBe('/api/v1/materiais/M1');
    expect(fetchMock.mock.calls[0][1]).toMatchObject({ method: 'PATCH' });
    expect(JSON.parse(String(fetchMock.mock.calls[0][1].body))).toEqual({
      titulo: 'Novo título',
      visibilidade: 'publicado',
    });
  });

  it('converte 422 de PATCH inválido em ErroApi com campos', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      json(
        {
          erro: {
            codigo: 'VALIDACAO',
            mensagem: 'Dados de entrada inválidos.',
            campos: { titulo: 'Mínimo de 3 caracteres' },
          },
        },
        422,
      ),
    );
    vi.stubGlobal('fetch', fetchMock);

    const erro = await httpApiClient
      .atualizarMaterial('M1', { titulo: 'ab' })
      .catch((e: unknown) => e);

    expect(erro).toBeInstanceOf(ErroApi);
    expect(erro).toMatchObject({
      status: 422,
      problema: {
        erro: { codigo: 'VALIDACAO', campos: { titulo: 'Mínimo de 3 caracteres' } },
      },
    });
  });

  it('converte 404 de material em ErroApi', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      json(
        {
          erro: {
            codigo: 'MATERIAL_NAO_ENCONTRADO',
            mensagem: 'Material não encontrado.',
          },
        },
        404,
      ),
    );
    vi.stubGlobal('fetch', fetchMock);

    const erro = await httpApiClient.obterMaterial('NAO_EXISTE').catch((e: unknown) => e);

    expect(erro).toBeInstanceOf(ErroApi);
    expect(erro).toMatchObject({
      status: 404,
      problema: { erro: { codigo: 'MATERIAL_NAO_ENCONTRADO' } },
    });
  });

  it('excluirMaterial devolve o resultado da remoção', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      json({ material_id: 'M1', removido: true, oci_removido: false, aviso: 'OCI indisponível' }),
    );
    vi.stubGlobal('fetch', fetchMock);

    const r = await httpApiClient.excluirMaterial('M1');

    expect(r.oci_removido).toBe(false);
    expect(r.material_id).toBe('M1');
    expect(fetchMock.mock.calls[0][0]).toBe('/api/v1/materiais/M1');
    expect(fetchMock.mock.calls[0][1]).toMatchObject({ method: 'DELETE' });
  });
});
