import { z } from 'zod';

export const LIMITES = {
  tituloMin: 3,
  tituloMax: 150,
  textoMin: 200,
  textoMax: 50_000,
  arquivoMaxBytes: 10 * 1024 * 1024,
  paginaPadrao: 12,
  paginaMax: 50,
} as const;

export const EXTENSOES_ACEITAS = ['.pdf', '.md', '.txt'] as const;

const dataIso = z
  .string()
  .refine(
    (v) => /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/.test(v) && !Number.isNaN(Date.parse(v)),
    'Data ISO 8601 inválida',
  );

export const perfilSchema = z.enum(['Iniciante', 'Desenvolvedor', 'LiderTecnico', 'Gestor']);
export const formatoSaidaSchema = z.enum(['Flashcards', 'Quiz', 'Tutorial', 'ResumoExecutivo']);
export const nichoSchema = z.enum(['Fintech', 'Saude', 'Ecommerce', 'Geral']);
export const nivelDetalheSchema = z.enum(['Didatico', 'Tecnico', 'Executivo']);
export const formatoExportacaoSchema = z.enum(['md', 'pdf', 'csv']);

export const tituloSchema = z
  .string()
  .trim()
  .min(LIMITES.tituloMin, 'Mínimo de 3 caracteres')
  .max(LIMITES.tituloMax, 'Máximo de 150 caracteres');

export const textoSchema = z
  .string()
  .trim()
  .min(LIMITES.textoMin, 'Mínimo de 200 caracteres')
  .max(LIMITES.textoMax, 'Máximo de 50.000 caracteres');

export const arquivoSchema = z
  .custom<File>((v) => typeof File !== 'undefined' && v instanceof File, { message: 'Selecione um arquivo.' })
  .refine((f) => f.size > 0, 'Arquivo vazio.')
  .refine((f) => f.size <= LIMITES.arquivoMaxBytes, 'Arquivo acima de 10 MB.')
  .refine(
    (f) => EXTENSOES_ACEITAS.some((ext) => f.name.toLowerCase().endsWith(ext)),
    'Use um arquivo .pdf, .md ou .txt.',
  );

export const AdaptacaoInputSchema = z
  .object({
    documento_titulo: tituloSchema,
    documento_conteudo: textoSchema,
    perfil_destinatario: perfilSchema,
    formato_saida: formatoSaidaSchema,
    nicho_setor: nichoSchema,
    nivel_detalhe: nivelDetalheSchema,
  })
  .strict();

export const AdaptacaoUploadInputSchema = z
  .object({
    arquivo: arquivoSchema,
    documento_titulo: tituloSchema,
    perfil_destinatario: perfilSchema,
    formato_saida: formatoSaidaSchema,
    nicho_setor: nichoSchema,
    nivel_detalhe: nivelDetalheSchema,
  })
  .strict();

export const FlashcardItemSchema = z
  .object({
    frente: z.string().trim().min(1),
    verso: z.string().trim().min(1),
    dica_didatica: z.string().trim().min(1).optional(),
  })
  .strict();

export const QuizItemSchema = z
  .object({
    pergunta: z.string().trim().min(1),
    opcoes: z.array(z.string().trim().min(1)).min(2).max(6),
    resposta_correta: z.number().int().min(0),
    explicacao: z.string().trim().min(1),
  })
  .strict();

export const ConteudoAdaptadoSchema = z.discriminatedUnion('tipo', [
  z
    .object({
      tipo: z.literal('flashcards'),
      titulo: z.string().min(1),
      introducao_contextualizada: z.string().min(1),
      itens: z.array(FlashcardItemSchema).min(3).max(30),
    })
    .strict(),
  z
    .object({
      tipo: z.literal('quiz'),
      titulo: z.string().min(1),
      introducao_contextualizada: z.string().min(1),
      itens: z.array(QuizItemSchema).min(1).max(20),
    })
    .strict(),
  z
    .object({
      tipo: z.literal('markdown'),
      titulo: z.string().min(1),
      introducao_contextualizada: z.string().min(1),
      itens: z.string().min(40),
    })
    .strict(),
]);

export const DocumentoRefSchema = z
  .object({
    titulo: z.string().min(1),
    origem: z.enum(['upload', 'texto']),
    nome_arquivo: z.string().min(1).optional(),
    tamanho_bytes: z.number().int().nonnegative().optional(),
  })
  .strict();

export const MetadadosSchema = z
  .object({
    perfil_aplicado: perfilSchema,
    formato_gerado: formatoSaidaSchema,
    nivel_detalhe_aplicado: nivelDetalheSchema,
    nicho_setor_aplicado: nichoSchema,
    tempo_estimado_estudo_minutos: z.number().int().min(1),
    conceitos_chave: z.array(z.string().min(1)).min(1).max(12),
  })
  .strict();

export const AvaliacaoQualidadeSchema = z
  .object({
    ancoragem_fonte_score: z.number().min(0).max(1),
    clareza_pedagogica: z.enum(['Alta', 'Media', 'Baixa']),
    observacoes: z.string().min(1).optional(),
  })
  .strict();

export const ArmazenamentoOciSchema = z
  .object({
    bucket: z.string().min(1),
    objeto_id: z.string().min(1),
    status_upload: z.enum(['concluido', 'falha']),
  })
  .strict();

export const CodigoErroSchema = z.enum([
  'VALIDACAO',
  'ARQUIVO_INVALIDO',
  'DOCUMENTO_ILEGIVEL',
  'LIMITE_EXCEDIDO',
  'ADAPTACAO_NAO_ENCONTRADA',
  'JOB_NAO_ENCONTRADO',
  'JOB_FINALIZADO',
  'FORMATO_INCOMPATIVEL',
  'FORMATO_DESCONHECIDO',
  'OCI_INDISPONIVEL',
  'INTERNO',
]);

export const ApiProblemaErroSchema = z
  .object({
    codigo: CodigoErroSchema,
    mensagem: z.string().min(1),
    campos: z.record(z.string(), z.string()).optional(),
    request_id: z.string().min(1).optional(),
  })
  .strict();

export const ApiProblemaSchema = z.object({ erro: ApiProblemaErroSchema }).strict();

const formatoParaTipo = {
  Flashcards: 'flashcards',
  Quiz: 'quiz',
  Tutorial: 'markdown',
  ResumoExecutivo: 'markdown',
} as const;

export const AdaptacaoPacoteSchema = z
  .object({
    adaptacao_id: z.string().min(1),
    status: z.literal('sucesso'),
    criado_em: dataIso,
    documento: DocumentoRefSchema,
    metadados: MetadadosSchema,
    conteudo_adaptado: ConteudoAdaptadoSchema,
    avaliacao_qualidade: AvaliacaoQualidadeSchema,
    armazenamento_oci: ArmazenamentoOciSchema,
  })
  .strict()
  .superRefine((pacote, ctx) => {
    const esperado = formatoParaTipo[pacote.metadados.formato_gerado];
    if (pacote.conteudo_adaptado.tipo !== esperado) {
      ctx.addIssue({
        code: 'custom',
        path: ['conteudo_adaptado', 'tipo'],
        message: `Formato ${pacote.metadados.formato_gerado} exige conteúdo ${esperado}.`,
      });
    }
    if (pacote.conteudo_adaptado.tipo === 'quiz') {
      pacote.conteudo_adaptado.itens.forEach((item, indice) => {
        if (item.resposta_correta >= item.opcoes.length) {
          ctx.addIssue({
            code: 'custom',
            path: ['conteudo_adaptado', 'itens', indice, 'resposta_correta'],
            message: 'resposta_correta fora do intervalo de opções.',
          });
        }
      });
    }
  });

export const EtapaJobSchema = z.enum([
  'extraindo',
  'chunking',
  'embeddings',
  'gerando',
  'revisando',
  'armazenando',
]);

export const JobRespostaSchema = z
  .object({
    job_id: z.string().min(1),
    status: z.enum(['queued', 'running', 'succeeded', 'failed', 'cancelled']),
    etapa_atual: EtapaJobSchema.nullable(),
    etapas_concluidas: z.array(EtapaJobSchema),
    progresso_percentual: z.number().min(0).max(100),
    mensagem: z.string().min(1).optional(),
    iniciado_em: dataIso,
    atualizado_em: dataIso,
    adaptacao_id: z.string().min(1).optional(),
    resultado: AdaptacaoPacoteSchema.optional(),
    erro: ApiProblemaErroSchema.optional(),
  })
  .strict()
  .superRefine((job, ctx) => {
    if (job.status === 'succeeded' && (!job.resultado || !job.adaptacao_id)) {
      ctx.addIssue({ code: 'custom', message: 'Job concluído exige resultado e adaptacao_id.' });
    }
    if (job.status === 'failed' && !job.erro) {
      ctx.addIssue({ code: 'custom', message: 'Job com falha exige erro.' });
    }
  });

export const AdaptacaoResumoSchema = z
  .object({
    adaptacao_id: z.string().min(1),
    criado_em: dataIso,
    documento: DocumentoRefSchema,
    perfil_aplicado: perfilSchema,
    formato_gerado: formatoSaidaSchema,
    nivel_detalhe_aplicado: nivelDetalheSchema,
    tempo_estimado_estudo_minutos: z.number().int().min(1),
    ancoragem_fonte_score: z.number().min(0).max(1),
    status_upload: z.enum(['concluido', 'falha']),
    conceitos_chave: z.array(z.string().min(1)).max(6),
  })
  .strict();

export const PaginaAdaptacoesSchema = z
  .object({
    itens: z.array(AdaptacaoResumoSchema),
    pagina: z.number().int().min(1),
    tamanho_pagina: z.number().int().min(1).max(LIMITES.paginaMax),
    total: z.number().int().min(0),
    total_paginas: z.number().int().min(0),
  })
  .strict();

export const OciStatusSchema = z
  .object({
    configurado: z.boolean(),
    bucket: z.string().min(1).optional(),
    regiao: z.string().min(1).optional(),
    total_objetos: z.number().int().min(0).optional(),
    bytes_armazenados: z.number().int().min(0).optional(),
    ultimo_upload_em: dataIso.optional(),
    mensagem: z.string().min(1).optional(),
    verificado_em: dataIso,
  })
  .strict();

export const HealthRespostaSchema = z
  .object({
    status: z.enum(['ok', 'degraded']),
    versao: z.string().min(1),
    oci: z.enum(['ok', 'indisponivel']),
    llm: z.enum(['ok', 'indisponivel']),
    verificado_em: dataIso,
  })
  .strict();
