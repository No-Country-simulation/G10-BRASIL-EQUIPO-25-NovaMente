// @vitest-environment node
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { afterAll, afterEach, beforeAll, describe, expect, it } from 'vitest';
import { httpApiClient } from './httpApiClient';
import { ErroApi, ErroContrato, ErroRede } from './erros';

const pacote = {
  adaptacao_id: '01javcnfCARD00000000001',
  status: 'sucesso',
  criado_em: '2026-10-21T14:02:11Z',
  documento: { titulo: 'VCN', origem: 'texto' },
  metadados: {
    perfil_aplicado: 'Iniciante',
    formato_gerado: 'Flashcards',
    nivel_detalhe_aplicado: 'Didatico',
    nicho_setor_aplicado: 'Geral',
    tempo_estimado_estudo_minutos: 5,
    conceitos_chave: ['VCN'],
  },
  conteudo_adaptado: {
    tipo: 'flashcards',
    titulo: 'VCN',
    introducao_contextualizada: 'Intro',
    itens: [
      { frente: 'a', verso: 'b' },
      { frente: 'c', verso: 'd' },
      { frente: 'e', verso: 'f' },
    ],
  },
  avaliacao_qualidade: { ancoragem_fonte_score: 0.98, clareza_pedagogica: 'Alta' },
  armazenamento_oci: { bucket: 'b', objeto_id: 'o.json', status_upload: 'concluido' },
};

const job = {
  job_id: 'j1',
  status: 'queued',
  etapa_atual: null,
  etapas_concluidas: [],
  progresso_percentual: 0,
  iniciado_em: '2026-10-21T14:02:11Z',
  atualizado_em: '2026-10-21T14:02:11Z',
};

let corpoRecebido: unknown = null;
let formRecebido: FormData | null = null;
let queryRecebida = '';

const server = setupServer(
  http.post('*/api/v1/adaptacoes', async ({ request }) => {
    corpoRecebido = await request.json();
    return HttpResponse.json(job, { status: 202 });
  }),
  http.post('*/api/v1/adaptacoes/upload', async ({ request }) => {
    formRecebido = await request.formData();
    return HttpResponse.json({ ...job, job_id: 'j2' }, { status: 202 });
  }),
  http.get('*/api/v1/adaptacoes', ({ request }) => {
    queryRecebida = new URL(request.url).search;
    return HttpResponse.json({ itens: [], pagina: 1, tamanho_pagina: 12, total: 0, total_paginas: 0 });
  }),
  http.get('*/api/v1/adaptacoes/:id', () => HttpResponse.json(pacote)),
  http.get('*/api/v1/adaptacoes/:id/download', () =>
    HttpResponse.json(pacote, { headers: { 'Content-Disposition': 'attachment; filename="x.json"' } }),
  ),
  http.get('*/api/v1/adaptacoes/:id/exportacao', () =>
    new HttpResponse('%PDF-1.4', {
      headers: { 'Content-Type': 'application/pdf' },
    }),
  ),
);

// O MSW substitui o fetch global no listen e, em ambiente node, o shim relativo
// do setup deixa de valer; reencapsulamos depois do listen para o cliente
// continuar chamando caminhos relativos. O ambiente node (em vez do jsdom) é
// necessário para o multipart: o File do jsdom trava o corpo no undici.
let fetchAnterior: typeof fetch;

beforeAll(() => {
  fetchAnterior = globalThis.fetch;
  server.listen();
  const fetchInterceptado = globalThis.fetch;
  globalThis.fetch = ((entrada: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof entrada === 'string' && entrada.startsWith('/') ? `http://localhost${entrada}` : entrada;
    return fetchInterceptado(url as RequestInfo, init);
  }) as typeof fetch;
});
afterEach(() => {
  server.resetHandlers();
  corpoRecebido = null;
  formRecebido = null;
  queryRecebida = '';
});
afterAll(() => {
  server.close();
  globalThis.fetch = fetchAnterior;
});

const entrada = {
  documento_titulo: 'VCN',
  documento_conteudo: 'a'.repeat(200),
  perfil_destinatario: 'Iniciante' as const,
  formato_saida: 'Flashcards' as const,
  nicho_setor: 'Geral' as const,
  nivel_detalhe: 'Didatico' as const,
};

describe('httpApiClient', () => {
  it('envia JSON para criação por texto', async () => {
    const resposta = await httpApiClient.criarPorTexto(entrada);
    expect(resposta.job_id).toBe('j1');
    expect(corpoRecebido).toEqual(entrada);
  });

  it('envia multipart sem documento_conteudo', async () => {
    const arquivo = new File(['abc'], 'manual.pdf', { type: 'application/pdf' });
    await httpApiClient.criarPorArquivo({ ...entrada, documento_conteudo: undefined, arquivo } as never);

    const arquivoRecebido = formRecebido?.get('arquivo');
    expect(arquivoRecebido).toBeInstanceOf(File);
    expect((arquivoRecebido as File).name).toBe('manual.pdf');
    expect(formRecebido?.get('documento_conteudo')).toBeNull();
    expect(formRecebido?.get('perfil_destinatario')).toBe('Iniciante');
  });

  it('monta query string só com filtros preenchidos', async () => {
    await httpApiClient.listar({ pagina: 2, formato: 'Quiz', q: '' });
    expect(queryRecebida).toContain('pagina=2');
    expect(queryRecebida).toContain('formato=Quiz');
    expect(queryRecebida).not.toContain('q=');
  });

  it('devolve blob no download do JSON', async () => {
    const blob = await httpApiClient.baixarJson('id1');
    expect(await blob.text()).toContain('"adaptacao_id"');
  });

  it('devolve blob na exportação', async () => {
    const blob = await httpApiClient.exportar('id1', 'pdf');
    expect(blob.type).toBe('application/pdf');
    expect(await blob.text()).toBe('%PDF-1.4');
  });

  it('converte erro 422 em ErroApi com campos', async () => {
    server.use(
      http.post('*/api/v1/adaptacoes', () =>
        HttpResponse.json(
          { erro: { codigo: 'VALIDACAO', mensagem: 'Dados inválidos', campos: { documento_titulo: 'Mínimo de 3' } } },
          { status: 422 },
        ),
      ),
    );
    const erro = await httpApiClient.criarPorTexto(entrada).catch((e: unknown) => e);
    expect(erro).toBeInstanceOf(ErroApi);
    expect(erro).toMatchObject({
      name: 'ErroApi',
      status: 422,
      problema: { erro: { campos: { documento_titulo: 'Mínimo de 3' } } },
    });
  });

  it('converte falha de rede em ErroRede', async () => {
    server.use(http.post('*/api/v1/adaptacoes', () => HttpResponse.error()));
    await expect(httpApiClient.criarPorTexto(entrada)).rejects.toBeInstanceOf(ErroRede);
  });

  it('converte resposta fora do schema em ErroContrato', async () => {
    server.use(http.get('*/api/v1/health', () => HttpResponse.json({ status: 'ok' })));
    await expect(httpApiClient.health()).rejects.toBeInstanceOf(ErroContrato);
  });
});
