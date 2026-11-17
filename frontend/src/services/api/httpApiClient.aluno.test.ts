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
    visibilidade: 'publicado',
    tempo_estimado_estudo_minutos: 5,
    ancoragem_fonte_score: 0.98,
    status_upload: 'concluido',
    criado_em: ISO,
    atualizado_em: ISO,
    ...extra,
  };
}

function itemCatalogo(extra: Record<string, unknown> = {}) {
  return {
    material_id: 'M1',
    titulo: 'Dominando Redes na Nuvem (VCN) do Zero',
    documento_titulo: 'Introdução à Arquitetura de Redes VCN na OCI',
    formato: 'Flashcards',
    perfil: 'Iniciante',
    nivel: 'Didatico',
    tempo_estimado_estudo_minutos: 5,
    criado_em: ISO,
    conceitos_chave: ['VCN', 'Sub-rede'],
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

function problema(codigo: string, mensagem: string, status: number): Response {
  return json({ erro: { codigo, mensagem } }, status);
}

afterEach(() => vi.unstubAllGlobals());

describe('httpApiClient — área do aluno', () => {
  it('lista a identificação sem e-mail', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(json({ itens: [{ aluno_id: 'A1', nome: 'Ana' }] }));
    vi.stubGlobal('fetch', fetchMock);

    const itens = await httpApiClient.listarIdentificacaoAluno();

    expect(itens).toEqual([{ aluno_id: 'A1', nome: 'Ana' }]);
    expect(fetchMock.mock.calls[0][0]).toBe('/api/v1/aluno/identificacao');
  });

  it('lista catálogo com aluno_id e filtros', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      json({
        itens: [],
        pagina: 1,
        tamanho_pagina: 12,
        total: 0,
        total_paginas: 0,
      }),
    );
    vi.stubGlobal('fetch', fetchMock);

    await httpApiClient.listarCatalogoAluno('A1', { formato: 'Quiz', q: 'vcn' });

    const url = String(fetchMock.mock.calls[0][0]);
    expect(url).toContain('/api/v1/aluno/materiais?aluno_id=A1');
    expect(url).toContain('formato=Quiz');
    expect(url).toContain('q=vcn');
  });

  it('lista catálogo com paginação, perfil e ordenação', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      json({
        itens: [itemCatalogo()],
        pagina: 2,
        tamanho_pagina: 5,
        total: 6,
        total_paginas: 2,
      }),
    );
    vi.stubGlobal('fetch', fetchMock);

    const pagina = await httpApiClient.listarCatalogoAluno('A1', {
      pagina: 2,
      tamanho_pagina: 5,
      perfil: 'Iniciante',
      ordenar: 'titulo:asc',
    });

    expect(pagina.total).toBe(6);
    expect(pagina.itens[0].conceitos_chave).toEqual(['VCN', 'Sub-rede']);
    const url = String(fetchMock.mock.calls[0][0]);
    expect(url).toContain('pagina=2');
    expect(url).toContain('tamanho_pagina=5');
    expect(url).toContain('perfil=Iniciante');
    expect(url).toContain('ordenar=titulo%3Aasc');
  });

  it('converte 403 de aluno inativo em ErroApi', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(problema('ALUNO_INATIVO', 'Aluno inativo.', 403)),
    );

    const erro = await httpApiClient.listarCatalogoAluno('A6').catch((e: unknown) => e);

    expect(erro).toBeInstanceOf(ErroApi);
    expect(erro).toMatchObject({
      status: 403,
      problema: { erro: { codigo: 'ALUNO_INATIVO' } },
    });
  });

  it('converte 404 de aluno inexistente em ErroApi', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(problema('ALUNO_NAO_ENCONTRADO', 'Aluno não encontrado.', 404)),
    );

    const erro = await httpApiClient.listarCatalogoAluno('NAO_EXISTE').catch((e: unknown) => e);

    expect(erro).toBeInstanceOf(ErroApi);
    expect(erro).toMatchObject({
      status: 404,
      problema: { erro: { codigo: 'ALUNO_NAO_ENCONTRADO' } },
    });
  });

  it('obtém o material do aluno com aluno_id na query', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      json({ material: materialResumo(), pacote: flashcardsFixture }),
    );
    vi.stubGlobal('fetch', fetchMock);

    const detalhe = await httpApiClient.obterMaterialAluno('A1', 'M1');

    expect(detalhe.material.material_id).toBe('M1');
    expect(detalhe.pacote.adaptacao_id).toBe(flashcardsFixture.adaptacao_id);
    expect(fetchMock.mock.calls[0][0]).toBe('/api/v1/aluno/materiais/M1?aluno_id=A1');
  });

  it('converte 404 de material não disponível em ErroApi', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        problema('MATERIAL_NAO_DISPONIVEL', 'Material não disponível.', 404),
      ),
    );

    const erro = await httpApiClient
      .obterMaterialAluno('A1', 'RASCUNHO')
      .catch((e: unknown) => e);

    expect(erro).toBeInstanceOf(ErroApi);
    expect(erro).toMatchObject({
      status: 404,
      problema: { erro: { codigo: 'MATERIAL_NAO_DISPONIVEL' } },
    });
  });
});
