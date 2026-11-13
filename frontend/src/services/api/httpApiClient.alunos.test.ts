// @vitest-environment node
import { afterEach, describe, expect, it, vi } from 'vitest';
import { httpApiClient } from './httpApiClient';
import { ErroApi } from './erros';

const ISO = '2026-11-09T12:00:00Z';

function aluno(extra: Record<string, unknown> = {}) {
  return {
    aluno_id: 'A1',
    nome: 'Ana',
    email: 'ana@exemplo.com',
    status: 'ativo',
    total_materiais: 0,
    criado_em: ISO,
    atualizado_em: ISO,
    ...extra,
  };
}

function vinculo(extra: Record<string, unknown> = {}) {
  return {
    material_id: 'M1',
    titulo: 'Material de VCN',
    formato: 'Flashcards',
    perfil: 'Iniciante',
    visibilidade: 'publicado',
    vinculado_em: ISO,
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

function semCorpo(status = 204): Response {
  return {
    ok: true,
    status,
    json: async () => {
      throw new Error('204 não tem corpo');
    },
  } as unknown as Response;
}

afterEach(() => vi.unstubAllGlobals());

describe('httpApiClient — alunos', () => {
  it('cria aluno e envia o corpo normalizado', async () => {
    const fetchMock = vi.fn().mockResolvedValue(json(aluno(), 201));
    vi.stubGlobal('fetch', fetchMock);

    const criado = await httpApiClient.criarAluno({
      nome: '  Ana  ',
      email: '  ANA@Exemplo.COM ',
    });

    expect(criado.aluno_id).toBe('A1');
    expect(fetchMock.mock.calls[0][0]).toBe('/api/v1/alunos');
    expect(fetchMock.mock.calls[0][1]).toMatchObject({ method: 'POST' });
    expect(JSON.parse(String(fetchMock.mock.calls[0][1].body))).toEqual({
      nome: 'Ana',
      email: 'ana@exemplo.com',
    });
  });

  it('lista alunos com paginação, filtros e ordenação', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      json({ itens: [aluno()], pagina: 2, tamanho_pagina: 5, total: 6, total_paginas: 2 }),
    );
    vi.stubGlobal('fetch', fetchMock);

    const pagina = await httpApiClient.listarAlunos({
      pagina: 2,
      tamanho_pagina: 5,
      q: 'ana',
      status: 'ativo',
      ordenar: 'nome:desc',
    });

    expect(pagina.total).toBe(6);
    const url = String(fetchMock.mock.calls[0][0]);
    expect(url.startsWith('/api/v1/alunos?')).toBe(true);
    expect(url).toContain('pagina=2');
    expect(url).toContain('tamanho_pagina=5');
    expect(url).toContain('q=ana');
    expect(url).toContain('status=ativo');
    expect(url).toContain('ordenar=nome%3Adesc');
  });

  it('obtém um aluno pelo id', async () => {
    const fetchMock = vi.fn().mockResolvedValue(json(aluno({ aluno_id: 'A7' })));
    vi.stubGlobal('fetch', fetchMock);

    const encontrado = await httpApiClient.obterAluno('A7');

    expect(encontrado.aluno_id).toBe('A7');
    expect(fetchMock.mock.calls[0][0]).toBe('/api/v1/alunos/A7');
  });

  it('atualiza aluno parcialmente com corpo normalizado', async () => {
    const fetchMock = vi.fn().mockResolvedValue(json(aluno({ status: 'inativo' })));
    vi.stubGlobal('fetch', fetchMock);

    const atualizado = await httpApiClient.atualizarAluno('A1', {
      email: '  BIA@Exemplo.COM ',
      status: 'inativo',
    });

    expect(atualizado.status).toBe('inativo');
    expect(fetchMock.mock.calls[0][0]).toBe('/api/v1/alunos/A1');
    expect(fetchMock.mock.calls[0][1]).toMatchObject({ method: 'PATCH' });
    expect(JSON.parse(String(fetchMock.mock.calls[0][1].body))).toEqual({
      email: 'bia@exemplo.com',
      status: 'inativo',
    });
  });

  it('excluirAluno aceita 204 sem corpo', async () => {
    const fetchMock = vi.fn().mockResolvedValue(semCorpo());
    vi.stubGlobal('fetch', fetchMock);

    await expect(httpApiClient.excluirAluno('A1')).resolves.toBeUndefined();

    expect(fetchMock.mock.calls[0][0]).toBe('/api/v1/alunos/A1');
    expect(fetchMock.mock.calls[0][1]).toMatchObject({ method: 'DELETE' });
  });

  it('converte 409 em ErroApi com campos.email', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      json(
        {
          erro: {
            codigo: 'EMAIL_JA_CADASTRADO',
            mensagem: 'E-mail já cadastrado.',
            campos: { email: 'E-mail já cadastrado.' },
          },
        },
        409,
      ),
    );
    vi.stubGlobal('fetch', fetchMock);

    const erro = await httpApiClient
      .criarAluno({ nome: 'Ana', email: 'ana@exemplo.com' })
      .catch((e: unknown) => e);

    expect(erro).toBeInstanceOf(ErroApi);
    expect(erro).toMatchObject({
      status: 409,
      problema: {
        erro: {
          codigo: 'EMAIL_JA_CADASTRADO',
          campos: { email: 'E-mail já cadastrado.' },
        },
      },
    });
  });

  it('lista os vínculos do aluno', async () => {
    const fetchMock = vi.fn().mockResolvedValue(json({ aluno_id: 'A1', itens: [vinculo()] }));
    vi.stubGlobal('fetch', fetchMock);

    const vinculos = await httpApiClient.listarVinculos('A1');

    expect(vinculos.itens[0].material_id).toBe('M1');
    expect(fetchMock.mock.calls[0][0]).toBe('/api/v1/alunos/A1/materiais');
  });

  it('substitui o conjunto de vínculos com PUT', async () => {
    const fetchMock = vi.fn().mockResolvedValue(json({ aluno_id: 'A1', itens: [] }));
    vi.stubGlobal('fetch', fetchMock);

    const vinculos = await httpApiClient.substituirVinculos('A1', {
      material_ids: ['M1', 'M2'],
    });

    expect(vinculos.itens).toEqual([]);
    expect(fetchMock.mock.calls[0][0]).toBe('/api/v1/alunos/A1/materiais');
    expect(fetchMock.mock.calls[0][1]).toMatchObject({ method: 'PUT' });
    expect(JSON.parse(String(fetchMock.mock.calls[0][1].body))).toEqual({
      material_ids: ['M1', 'M2'],
    });
  });

  it('adiciona vínculo e devolve o material', async () => {
    const fetchMock = vi.fn().mockResolvedValue(json(vinculo(), 201));
    vi.stubGlobal('fetch', fetchMock);

    const criado = await httpApiClient.adicionarVinculo('A1', 'M1');

    expect(criado.titulo).toBe('Material de VCN');
    expect(fetchMock.mock.calls[0][0]).toBe('/api/v1/alunos/A1/materiais/M1');
    expect(fetchMock.mock.calls[0][1]).toMatchObject({ method: 'POST' });
  });

  it('remove vínculo e aceita 204 sem corpo', async () => {
    const fetchMock = vi.fn().mockResolvedValue(semCorpo());
    vi.stubGlobal('fetch', fetchMock);

    await expect(httpApiClient.removerVinculo('A1', 'M1')).resolves.toBeUndefined();

    expect(fetchMock.mock.calls[0][0]).toBe('/api/v1/alunos/A1/materiais/M1');
    expect(fetchMock.mock.calls[0][1]).toMatchObject({ method: 'DELETE' });
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

    const erro = await httpApiClient.adicionarVinculo('A1', 'NAO_EXISTE').catch((e: unknown) => e);

    expect(erro).toMatchObject({
      status: 404,
      problema: { erro: { codigo: 'MATERIAL_NAO_ENCONTRADO' } },
    });
  });
});
