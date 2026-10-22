// @vitest-environment node
import { afterAll, afterEach, beforeAll, describe, expect, it } from 'vitest';
import { server } from './server';
import { configurarDuracaoJob, limparEstadoMock, semearHistorico } from './estadoJobs';
import { httpApiClient } from '@/services/api/httpApiClient';
import { ErroApi } from '@/services/api/erros';
import { LIMITES } from '@/types/schemas';

const entrada = {
  documento_titulo: 'Introdução à VCN',
  documento_conteudo: 'A '.repeat(120),
  perfil_destinatario: 'Iniciante' as const,
  formato_saida: 'Flashcards' as const,
  nicho_setor: 'Geral' as const,
  nivel_detalhe: 'Didatico' as const,
};

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
afterEach(() => {
  server.resetHandlers();
  limparEstadoMock();
  configurarDuracaoJob(6000);
});
afterAll(() => {
  server.close();
  globalThis.fetch = fetchAnterior;
});

describe('handlers de adaptação', () => {
  it('cria job em 202 e conclui com pacote válido', async () => {
    configurarDuracaoJob(30);
    const criado = await httpApiClient.criarPorTexto(entrada);
    expect(criado.status).toBe('queued');

    await new Promise((r) => setTimeout(r, 60));
    const job = await httpApiClient.obterJob(criado.job_id);

    expect(job.status).toBe('succeeded');
    expect(job.resultado?.metadados.formato_gerado).toBe('Flashcards');
    expect(job.resultado?.documento.titulo).toBe(entrada.documento_titulo);
    expect(job.progresso_percentual).toBe(100);

    const pacote = await httpApiClient.obter(job.adaptacao_id!);
    expect(pacote.conteudo_adaptado.tipo).toBe('flashcards');
  });

  it('respeita limite de texto com 422 e campos', async () => {
    const erro = await httpApiClient
      .criarPorTexto({ ...entrada, documento_conteudo: 'x' })
      .catch((e: unknown) => e);
    expect(erro).toMatchObject({
      status: 422,
      problema: { erro: { codigo: 'VALIDACAO' } },
    });
    expect((erro as ErroApi).problema.erro.campos).toHaveProperty('documento_conteudo');
  });

  it('aceita upload válido e conclui com metadados do arquivo', async () => {
    configurarDuracaoJob(30);
    const conteudo = '# VCN\n\nA VCN é uma rede privada.';
    const arquivo = new File([conteudo], 'vcn.md', { type: 'text/markdown' });
    const criado = await httpApiClient.criarPorArquivo({
      ...entrada,
      documento_conteudo: undefined,
      arquivo,
    } as never);
    expect(criado.status).toBe('queued');

    await new Promise((r) => setTimeout(r, 60));
    const job = await httpApiClient.obterJob(criado.job_id);
    expect(job.status).toBe('succeeded');
    expect(job.resultado?.documento.origem).toBe('upload');
    expect(job.resultado?.documento.nome_arquivo).toBe('vcn.md');
    expect(job.resultado?.documento.tamanho_bytes).toBe(arquivo.size);
  });

  it('rejeita arquivo acima de 10 MB com 413', async () => {
    const arquivo = new File([new Uint8Array(LIMITES.arquivoMaxBytes + 1)], 'grande.pdf');
    await expect(
      httpApiClient.criarPorArquivo({ ...entrada, documento_conteudo: undefined, arquivo } as never),
    ).rejects.toMatchObject({ status: 413, problema: { erro: { codigo: 'LIMITE_EXCEDIDO' } } });
  });

  it('rejeita extensão inválida no upload com 415', async () => {
    const arquivo = new File(['x'], 'manual.docx');
    await expect(
      httpApiClient.criarPorArquivo({ ...entrada, documento_conteudo: undefined, arquivo } as never),
    ).rejects.toMatchObject({ status: 415, problema: { erro: { codigo: 'ARQUIVO_INVALIDO' } } });
  });

  it('cancela job em andamento e recusa cancelar finalizado', async () => {
    configurarDuracaoJob(60_000);
    const criado = await httpApiClient.criarPorTexto(entrada);
    const cancelado = await httpApiClient.cancelarJob(criado.job_id);
    expect(cancelado.status).toBe('cancelled');
    await expect(httpApiClient.cancelarJob(criado.job_id)).rejects.toMatchObject({ status: 409 });
  });

  it('pagina e filtra o histórico', async () => {
    semearHistorico(14);
    const pagina1 = await httpApiClient.listar({ pagina: 1, tamanho_pagina: 12 });
    expect(pagina1.itens).toHaveLength(12);
    expect(pagina1.total_paginas).toBe(2);
    const soQuiz = await httpApiClient.listar({ formato: 'Quiz' });
    expect(soQuiz.itens.length).toBeGreaterThan(0);
    expect(soQuiz.itens.every((i) => i.formato_gerado === 'Quiz')).toBe(true);
  });

  it('exporta csv só para flashcards', async () => {
    configurarDuracaoJob(10);
    const criado = await httpApiClient.criarPorTexto({ ...entrada, formato_saida: 'ResumoExecutivo' });
    await new Promise((r) => setTimeout(r, 30));
    const job = await httpApiClient.obterJob(criado.job_id);
    await expect(httpApiClient.exportar(job.adaptacao_id!, 'csv')).rejects.toMatchObject({ status: 409 });
  });
});
