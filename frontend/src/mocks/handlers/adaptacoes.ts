import { http, HttpResponse } from 'msw';
import flashcards from '../fixtures/flashcards-vcn-iniciante.json';
import quiz from '../fixtures/quiz-vcn-desenvolvedor.json';
import tutorial from '../fixtures/tutorial-vcn-lider.json';
import resumo from '../fixtures/resumo-vcn-gestor.json';
import {
  AdaptacaoInputSchema,
  formatoSaidaSchema,
  perfilSchema,
  LIMITES,
} from '@/types/schemas';
import type { AdaptacaoInput, AdaptacaoPacote, FormatoSaida } from '@/types/novamente';
import {
  criarJob,
  listarPacotes,
  obterPacote,
  registrarPacote,
  resumir as resumirPacote,
} from '../estadoJobs';
import { nomeArquivoExportacao, nomeArquivoPacote } from '@/lib/formatadores';

const POR_FORMATO: Record<FormatoSaida, unknown> = {
  Flashcards: flashcards,
  Quiz: quiz,
  Tutorial: tutorial,
  ResumoExecutivo: resumo,
};

function problemas(campos: Record<string, string>) {
  return HttpResponse.json(
    { erro: { codigo: 'VALIDACAO', mensagem: 'Dados inválidos', campos } },
    { status: 422 },
  );
}

function naoEncontrado() {
  return HttpResponse.json(
    { erro: { codigo: 'ADAPTACAO_NAO_ENCONTRADA', mensagem: 'Material não encontrado.' } },
    { status: 404 },
  );
}

// O `File` do jsdom não é o mesmo do undici, então não usamos `instanceof File`:
// reconhecemos o arquivo pela forma (duck typing) no multipart.
interface ArquivoLike {
  name: string;
  size: number;
  arrayBuffer: () => Promise<ArrayBuffer>;
}

function ehArquivo(valor: unknown): valor is ArquivoLike {
  return (
    typeof valor === 'object' &&
    valor !== null &&
    'arrayBuffer' in valor &&
    'name' in valor &&
    'size' in valor &&
    typeof (valor as ArquivoLike).name === 'string' &&
    typeof (valor as ArquivoLike).size === 'number'
  );
}

let contadorPacotes = 0;

function montarPacote(
  entrada: AdaptacaoInput,
  extra: Partial<AdaptacaoPacote['documento']> = {},
): AdaptacaoPacote {
  const base = structuredClone(POR_FORMATO[entrada.formato_saida]) as AdaptacaoPacote;
  contadorPacotes += 1;
  const id = `01J${Date.now().toString(36).toUpperCase()}${String(contadorPacotes).padStart(12, '0')}`
    .toUpperCase()
    .slice(0, 26);
  const pacote: AdaptacaoPacote = {
    ...base,
    adaptacao_id: id,
    criado_em: new Date().toISOString(),
    documento: { titulo: entrada.documento_titulo, origem: 'texto', ...extra },
    metadados: {
      ...base.metadados,
      perfil_aplicado: entrada.perfil_destinatario,
      formato_gerado: entrada.formato_saida,
      nivel_detalhe_aplicado: entrada.nivel_detalhe,
      nicho_setor_aplicado: entrada.nicho_setor,
    },
  };
  return {
    ...pacote,
    armazenamento_oci: { ...pacote.armazenamento_oci, objeto_id: nomeArquivoPacote(pacote) },
  };
}

export const handlersAdaptacoes = [
  http.post('*/api/v1/adaptacoes', async ({ request }) => {
    const corpo = (await request.json()) as { documento_conteudo?: unknown };
    // Acima de 50.000 caracteres a spec manda 413 (LIMITE_EXCEDIDO), não 422.
    if (
      typeof corpo?.documento_conteudo === 'string' &&
      corpo.documento_conteudo.trim().length > LIMITES.textoMax
    ) {
      return HttpResponse.json(
        {
          erro: {
            codigo: 'LIMITE_EXCEDIDO',
            mensagem: 'Texto acima de 50.000 caracteres.',
            campos: { documento_conteudo: 'Texto acima de 50.000 caracteres.' },
          },
        },
        { status: 413 },
      );
    }
    const analisado = AdaptacaoInputSchema.safeParse(corpo);
    if (!analisado.success) {
      const campos = Object.fromEntries(analisado.error.issues.map((i) => [i.path.join('.'), i.message]));
      return problemas(campos);
    }
    const pacote = montarPacote(analisado.data);
    const job = criarJob(pacote);
    return HttpResponse.json(job, { status: 202, headers: { Location: `/api/v1/jobs/${job.job_id}` } });
  }),

  http.post('*/api/v1/adaptacoes/upload', async ({ request }) => {
    const form = await request.formData();
    const arquivo = form.get('arquivo');
    if (!ehArquivo(arquivo)) {
      return problemas({ arquivo: 'Selecione um arquivo.' });
    }
    if (arquivo.size > LIMITES.arquivoMaxBytes) {
      return HttpResponse.json(
        {
          erro: {
            codigo: 'LIMITE_EXCEDIDO',
            mensagem: 'Arquivo acima de 10 MB.',
            campos: { arquivo: 'Arquivo acima de 10 MB.' },
          },
        },
        { status: 413 },
      );
    }
    if (!/\.(pdf|md|txt)$/i.test(arquivo.name)) {
      return HttpResponse.json(
        {
          erro: {
            codigo: 'ARQUIVO_INVALIDO',
            mensagem: 'Use um arquivo .pdf, .md ou .txt.',
            campos: { arquivo: 'Formato não suportado.' },
          },
        },
        { status: 415 },
      );
    }
    if (form.has('documento_conteudo')) {
      return problemas({ documento_conteudo: 'não permitido quando há arquivo' });
    }
    const entrada = {
      documento_titulo: String(form.get('documento_titulo') ?? ''),
      documento_conteudo: 'a'.repeat(200),
      perfil_destinatario: String(form.get('perfil_destinatario')),
      formato_saida: String(form.get('formato_saida')),
      nicho_setor: String(form.get('nicho_setor')),
      nivel_detalhe: String(form.get('nivel_detalhe')),
    };
    const analisado = AdaptacaoInputSchema.safeParse(entrada);
    if (!analisado.success) {
      return problemas({ documento_titulo: 'Informe um título válido.' });
    }
    const pacote = montarPacote(analisado.data, {
      origem: 'upload',
      nome_arquivo: arquivo.name,
      tamanho_bytes: arquivo.size,
    });
    const job = criarJob(pacote);
    return HttpResponse.json(job, { status: 202, headers: { Location: `/api/v1/jobs/${job.job_id}` } });
  }),

  http.get('*/api/v1/adaptacoes', ({ request }) => {
    const url = new URL(request.url);
    const campos: Record<string, string> = {};

    function inteiro(bruto: string | null, padrao: number, minimo: number, maximo: number): number | null {
      if (bruto === null || bruto === '') return padrao;
      if (!/^\d+$/.test(bruto)) return null;
      const numero = Number(bruto);
      return numero >= minimo && numero <= maximo ? numero : null;
    }

    const pagina = inteiro(url.searchParams.get('pagina'), 1, 1, Number.MAX_SAFE_INTEGER);
    if (pagina === null) campos.pagina = 'Deve ser um inteiro maior ou igual a 1.';
    const tamanho = inteiro(
      url.searchParams.get('tamanho_pagina'),
      LIMITES.paginaPadrao,
      1,
      LIMITES.paginaMax,
    );
    if (tamanho === null) campos.tamanho_pagina = `Deve estar entre 1 e ${LIMITES.paginaMax}.`;

    const formato = url.searchParams.get('formato');
    if (formato && !formatoSaidaSchema.safeParse(formato).success) {
      campos.formato = 'Formato de saída desconhecido.';
    }
    const perfil = url.searchParams.get('perfil');
    if (perfil && !perfilSchema.safeParse(perfil).success) {
      campos.perfil = 'Perfil desconhecido.';
    }

    const q = (url.searchParams.get('q') ?? '').trim();
    if (q.length > 100) campos.q = 'Máximo de 100 caracteres.';

    const ordenar = url.searchParams.get('ordenar') ?? 'criado_em:desc';
    if (!['criado_em:desc', 'criado_em:asc', 'ancoragem:desc'].includes(ordenar)) {
      campos.ordenar = 'Ordenação desconhecida.';
    }

    if (Object.keys(campos).length > 0) return problemas(campos);

    // Depois da validação, nulos só existiriam se houvesse erro — e já saímos.
    const paginaAtual = pagina ?? 1;
    const tamanhoAtual = tamanho ?? LIMITES.paginaPadrao;

    const todos = listarPacotes()
      .map((p) => ({ p, resumo: resumirPacote(p) }))
      .filter(({ resumo }) => (formato ? resumo.formato_gerado === formato : true))
      .filter(({ resumo }) => (perfil ? resumo.perfil_aplicado === perfil : true))
      .filter(({ resumo }) =>
        q
          ? resumo.documento.titulo.toLowerCase().includes(q.toLowerCase()) ||
            resumo.conceitos_chave.join(' ').toLowerCase().includes(q.toLowerCase())
          : true,
      )
      .sort((a, b) =>
        ordenar === 'criado_em:asc'
          ? Date.parse(a.resumo.criado_em) - Date.parse(b.resumo.criado_em)
          : ordenar === 'ancoragem:desc'
            ? b.resumo.ancoragem_fonte_score - a.resumo.ancoragem_fonte_score
            : Date.parse(b.resumo.criado_em) - Date.parse(a.resumo.criado_em),
      );

    const inicio = (paginaAtual - 1) * tamanhoAtual;
    return HttpResponse.json({
      itens: todos.slice(inicio, inicio + tamanhoAtual).map(({ resumo }) => resumo),
      pagina: paginaAtual,
      tamanho_pagina: tamanhoAtual,
      total: todos.length,
      total_paginas: Math.ceil(todos.length / tamanhoAtual),
    });
  }),

  http.get('*/api/v1/adaptacoes/:id', ({ params }) => {
    const pacote = obterPacote(String(params.id));
    if (!pacote) return naoEncontrado();
    return HttpResponse.json(pacote);
  }),

  http.get('*/api/v1/adaptacoes/:id/download', ({ params }) => {
    const pacote = obterPacote(String(params.id));
    if (!pacote) return naoEncontrado();
    return HttpResponse.json(pacote, {
      headers: { 'Content-Disposition': `attachment; filename="${nomeArquivoPacote(pacote)}"` },
    });
  }),

  http.get('*/api/v1/adaptacoes/:id/exportacao', ({ params, request }) => {
    const pacote = obterPacote(String(params.id));
    if (!pacote) return naoEncontrado();

    const formato = new URL(request.url).searchParams.get('formato');
    if (formato === 'csv') {
      if (pacote.conteudo_adaptado.tipo !== 'flashcards') {
        return HttpResponse.json(
          {
            erro: {
              codigo: 'FORMATO_INCOMPATIVEL',
              mensagem: 'CSV está disponível apenas para Flashcards.',
            },
          },
          { status: 409 },
        );
      }
      const linhas = ['frente;verso;dica'];
      // Aspas duplas como escape (RFC 4180/Anki): `"` vira `""` dentro do campo.
      const campo = (valor: string) => `"${valor.replace(/"/g, '""')}"`;
      pacote.conteudo_adaptado.itens.forEach((i) =>
        linhas.push(`${campo(i.frente)};${campo(i.verso)};${campo(i.dica_didatica ?? '')}`),
      );
      return new HttpResponse(linhas.join('\n'), {
        headers: {
          'Content-Type': 'text/csv; charset=utf-8',
          'Content-Disposition': `attachment; filename="${nomeArquivoExportacao(pacote, 'csv')}"`,
        },
      });
    }
    if (formato === 'md') {
      const conteudo = pacote.conteudo_adaptado;
      const corpo =
        conteudo.tipo === 'markdown'
          ? conteudo.itens
          : conteudo.tipo === 'flashcards'
            ? conteudo.itens.map((i) => `### ${i.frente}\n\n${i.verso}`).join('\n\n')
            : conteudo.itens
                .map(
                  (q) =>
                    `### ${q.pergunta}\n\n${q.opcoes.map((o, n) => `${n + 1}. ${o}`).join('\n')}\n\n_${q.explicacao}_`,
                )
                .join('\n\n');
      return new HttpResponse(
        `# ${conteudo.titulo}\n\n${conteudo.introducao_contextualizada}\n\n${corpo}\n`,
        {
          headers: {
            'Content-Type': 'text/markdown; charset=utf-8',
            'Content-Disposition': `attachment; filename="${nomeArquivoExportacao(pacote, 'md')}"`,
          },
        },
      );
    }
    if (formato === 'pdf') {
      return new HttpResponse('%PDF-1.4\n% mock\n', {
        headers: {
          'Content-Type': 'application/pdf',
          'Content-Disposition': `attachment; filename="${nomeArquivoExportacao(pacote, 'pdf')}"`,
        },
      });
    }
    return HttpResponse.json(
      {
        erro: {
          codigo: 'FORMATO_DESCONHECIDO',
          mensagem: 'Formato de exportação desconhecido.',
        },
      },
      { status: 400 },
    );
  }),
];

// Semeia o histórico com um pacote já concluído, para a demo nunca abrir vazia.
registrarPacote(flashcards as unknown as AdaptacaoPacote);
