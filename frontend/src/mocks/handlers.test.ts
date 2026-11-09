// @vitest-environment node
import { afterAll, afterEach, beforeAll, describe, expect, it } from 'vitest';
import { server } from './server';
import { configurarDuracaoJob, limparEstadoMock, registrarPacote, semearHistorico } from './estadoJobs';
import flashcardsFixture from './fixtures/flashcards-vcn-iniciante.json';
import type { AdaptacaoPacote } from '@/types/novamente';
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

  it.each(['Quiz', 'Tutorial', 'ResumoExecutivo'] as const)('exporta csv só para flashcards (409 em %s)', async (formato) => {
    configurarDuracaoJob(10);
    const criado = await httpApiClient.criarPorTexto({ ...entrada, formato_saida: formato });
    await new Promise((r) => setTimeout(r, 30));
    const job = await httpApiClient.obterJob(criado.job_id);
    await expect(httpApiClient.exportar(job.adaptacao_id!, 'csv')).rejects.toMatchObject({ status: 409 });
  });

  it('responde 413 quando o texto passa de 50.000 caracteres', async () => {
    await expect(
      httpApiClient.criarPorTexto({ ...entrada, documento_conteudo: 'x'.repeat(LIMITES.textoMax + 1) }),
    ).rejects.toMatchObject({ status: 413, problema: { erro: { codigo: 'LIMITE_EXCEDIDO' } } });
  });

  it('responde 422 com campos em query fora da faixa', async () => {
    const erro = await httpApiClient
      .listar({ tamanho_pagina: LIMITES.paginaMax + 1 })
      .catch((e: unknown) => e);
    expect(erro).toMatchObject({ status: 422, problema: { erro: { codigo: 'VALIDACAO' } } });
    expect((erro as ErroApi).problema.erro.campos).toHaveProperty('tamanho_pagina');

    const ordenacao = await httpApiClient
      .listar({ ordenar: 'desconhecida' as never })
      .catch((e: unknown) => e);
    expect((ordenacao as ErroApi).problema.erro.campos).toHaveProperty('ordenar');
  });

  it('ordena o histórico por ancoragem', async () => {
    semearHistorico(4);
    const pagina = await httpApiClient.listar({ ordenar: 'ancoragem:desc' });
    const notas = pagina.itens.map((i) => i.ancoragem_fonte_score);
    expect(notas).toEqual([...notas].sort((a, b) => b - a));
  });

  it('nomeia o download com documento, perfil, formato e id8', async () => {
    semearHistorico(1);
    const [item] = (await httpApiClient.listar({})).itens;
    const resposta = await fetch(`/api/v1/adaptacoes/${item.adaptacao_id}/download`);
    expect(resposta.status).toBe(200);
    expect(resposta.headers.get('Content-Disposition')).toContain(
      'novamente-manual-de-exemplo-1-iniciante-flashcards-01jseed0.json',
    );
  });

  it('nomeia a exportação com o mesmo padrão do download', async () => {
    semearHistorico(1);
    const [item] = (await httpApiClient.listar({})).itens;
    const resposta = await fetch(`/api/v1/adaptacoes/${item.adaptacao_id}/exportacao?formato=md`);
    expect(resposta.status).toBe(200);
    expect(resposta.headers.get('Content-Disposition')).toContain(
      'novamente-manual-de-exemplo-1-iniciante-flashcards-01jseed0.md',
    );
  });

  describe('CSV de flashcards no formato Anki', () => {
    type Cartao = { frente: string; verso: string; dica_didatica?: string | null };

    async function exportarCsv(itens: Cartao[], id: string) {
      const pacote = structuredClone(flashcardsFixture) as unknown as AdaptacaoPacote;
      if (pacote.conteudo_adaptado.tipo === 'flashcards') pacote.conteudo_adaptado.itens = itens;
      pacote.adaptacao_id = id;
      registrarPacote(pacote);
      const resposta = await fetch(`/api/v1/adaptacoes/${id}/exportacao?formato=csv`);
      return { resposta, csv: await resposta.text() };
    }

    // Mesmos cartões e mesmo texto esperado do backend (gerar_csv).
    const CARTOES: Cartao[] = [
      { frente: 'O que faz o método GET?', verso: 'Busca um recurso sem alterá-lo.', dica_didatica: 'Pense em leitura.' },
      { frente: 'O que é o método "POST"?', verso: 'Cria um recurso novo; os dados vão no corpo.', dica_didatica: null },
      {
        frente: 'O que indica o código 404?',
        verso: 'Recurso não encontrado (erro do cliente).',
        dica_didatica: 'Família 4xx = erro de quem pediu.',
      },
      {
        frente: 'Como se escreve uma tag <br> e o símbolo &?',
        verso: 'Em HTML: &lt;br&gt; e &amp;amp;',
        dica_didatica: 'Texto com < > & é escapado.',
      },
    ];
    const ESPERADO =
      '#separator:Semicolon\n' +
      '#html:true\n' +
      '"O que faz o método GET?";"Busca um recurso sem alterá-lo.<br><br><small><b>Dica:</b> <i>Pense em leitura.</i></small>"\n' +
      '"O que é o método ""POST""?";"Cria um recurso novo; os dados vão no corpo."\n' +
      '"O que indica o código 404?";"Recurso não encontrado (erro do cliente).<br><br><small><b>Dica:</b> <i>Família 4xx = erro de quem pediu.</i></small>"\n' +
      '"Como se escreve uma tag &lt;br&gt; e o símbolo &amp;?";"Em HTML: &amp;lt;br&amp;gt; e &amp;amp;amp;<br><br><small><b>Dica:</b> <i>Texto com &lt; &gt; &amp; é escapado.</i></small>"\n';

    // Leitor CSV mínimo para `;` com campos entre aspas e `""` como escape.
    function lerCsv(texto: string): string[][] {
      return texto
        .split('\n')
        .filter((linha) => linha !== '' && !linha.startsWith('#'))
        .map((linha) => {
          const campos: string[] = [];
          let atual = '';
          let entreAspas = false;
          for (let i = 0; i < linha.length; i += 1) {
            const c = linha[i];
            if (entreAspas && c === '"' && linha[i + 1] === '"') {
              atual += '"';
              i += 1;
            } else if (c === '"') {
              entreAspas = !entreAspas;
            } else if (c === ';' && !entreAspas) {
              campos.push(atual);
              atual = '';
            } else {
              atual += c;
            }
          }
          campos.push(atual);
          return campos;
        });
    }

    it('gera exatamente o mesmo texto do backend', async () => {
      const { resposta, csv } = await exportarCsv(CARTOES, '01JCSVTESTE0000000000001');
      expect(resposta.status).toBe(200);
      expect(csv).toBe(ESPERADO);
      expect(resposta.headers.get('Content-Type')).toBe('text/csv; charset=utf-8');
      expect(resposta.headers.get('Content-Disposition')).toContain('.csv"');
    });

    it('não tem linha de cabeçalho', async () => {
      const { csv } = await exportarCsv(CARTOES, '01JCSVTESTE0000000000002');
      expect(csv.split('\n').some((linha) => linha.startsWith('frente'))).toBe(false);
    });

    it('cartão sem dica não ganha rodapé no verso', async () => {
      const { csv } = await exportarCsv(CARTOES, '01JCSVTESTE0000000000003');
      const [, versoSemDica] = lerCsv(csv)[1];
      expect(versoSemDica).toBe('Cria um recurso novo; os dados vão no corpo.');
      expect(versoSemDica).not.toContain('<br>');
      expect(versoSemDica).not.toContain('Dica');
    });

    it('escapa HTML do conteúdo', async () => {
      const perigoso = '<script>alert(1)</script> P&D';
      const { csv } = await exportarCsv(
        [
          { frente: perigoso, verso: perigoso, dica_didatica: perigoso },
          ...CARTOES.slice(0, 2),
        ],
        '01JCSVTESTE0000000000004',
      );
      expect(csv).not.toContain('<script>');
      expect(csv.split('&lt;script&gt;alert(1)&lt;/script&gt; P&amp;D')).toHaveLength(4);
    });

    it('lido de volta, cada cartão vira uma linha de duas colunas', async () => {
      const { csv } = await exportarCsv(CARTOES, '01JCSVTESTE0000000000005');
      const linhas = lerCsv(csv);
      expect(linhas).toHaveLength(CARTOES.length);
      linhas.forEach((colunas, i) => {
        expect(colunas).toHaveLength(2);
        expect(colunas[1].startsWith(
          CARTOES[i].verso.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'),
        )).toBe(true);
      });
      expect(linhas[1][0]).toBe('O que é o método "POST"?');
    });

    it('usa os cartões da fixture sem perder nenhum', async () => {
      const fixture = flashcardsFixture as unknown as AdaptacaoPacote;
      const itens = fixture.conteudo_adaptado.tipo === 'flashcards' ? fixture.conteudo_adaptado.itens : [];
      const { csv } = await exportarCsv(structuredClone(itens), '01JCSVTESTE0000000000006');
      expect(csv.startsWith('#separator:Semicolon\n#html:true\n')).toBe(true);
      expect(lerCsv(csv)).toHaveLength(itens.length);
    });
  });
});
