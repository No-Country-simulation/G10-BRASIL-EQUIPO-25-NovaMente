import { http, HttpResponse } from 'msw';
import flashcards from '../fixtures/flashcards-vcn-iniciante.json';
import quiz from '../fixtures/quiz-vcn-desenvolvedor.json';
import tutorial from '../fixtures/tutorial-vcn-lider.json';
import resumo from '../fixtures/resumo-vcn-gestor.json';
import { AdaptacaoInputSchema } from '@/types/schemas';
import type { AdaptacaoInput, AdaptacaoPacote, FormatoSaida } from '@/types/novamente';
import {
  criarJob,
  listarPacotes,
  obterPacote,
  registrarPacote,
  resumir as resumirPacote,
} from '../estadoJobs';
import { nomeArquivoPacote } from '@/lib/formatadores';

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
    const corpo = await request.json();
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
    if (arquivo.size > 10 * 1024 * 1024) {
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
    const pagina = Math.max(1, Number(url.searchParams.get('pagina') ?? 1));
    const tamanho = Math.min(50, Math.max(1, Number(url.searchParams.get('tamanho_pagina') ?? 12)));
    const formato = url.searchParams.get('formato');
    const perfil = url.searchParams.get('perfil');
    const q = (url.searchParams.get('q') ?? '').toLowerCase();

    const todos = listarPacotes()
      .map((p) => ({ p, resumo: resumirPacote(p) }))
      .filter(({ resumo }) => (formato ? resumo.formato_gerado === formato : true))
      .filter(({ resumo }) => (perfil ? resumo.perfil_aplicado === perfil : true))
      .filter(({ resumo }) =>
        q
          ? resumo.documento.titulo.toLowerCase().includes(q) ||
            resumo.conceitos_chave.join(' ').toLowerCase().includes(q)
          : true,
      )
      .sort((a, b) => Date.parse(b.resumo.criado_em) - Date.parse(a.resumo.criado_em));

    const inicio = (pagina - 1) * tamanho;
    return HttpResponse.json({
      itens: todos.slice(inicio, inicio + tamanho).map(({ resumo }) => resumo),
      pagina,
      tamanho_pagina: tamanho,
      total: todos.length,
      total_paginas: Math.ceil(todos.length / tamanho),
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
      headers: { 'Content-Disposition': `attachment; filename="${pacote.adaptacao_id}.json"` },
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
      pacote.conteudo_adaptado.itens.forEach((i) =>
        linhas.push(`"${i.frente}";"${i.verso}";"${i.dica_didatica ?? ''}"`),
      );
      return new HttpResponse(linhas.join('\n'), {
        headers: { 'Content-Type': 'text/csv; charset=utf-8' },
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
        { headers: { 'Content-Type': 'text/markdown; charset=utf-8' } },
      );
    }
    if (formato === 'pdf') {
      return new HttpResponse('%PDF-1.4\n% mock\n', {
        headers: { 'Content-Type': 'application/pdf' },
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
