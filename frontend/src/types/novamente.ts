import type { z } from 'zod';
import type {
  AdaptacaoInputSchema,
  AdaptacaoPacoteSchema,
  AdaptacaoResumoSchema,
  AdaptacaoUploadInputSchema,
  ApiProblemaErroSchema,
  EtapaJobSchema,
  HealthRespostaSchema,
  JobRespostaSchema,
  OciStatusSchema,
  PaginaAdaptacoesSchema,
  perfilSchema,
  formatoSaidaSchema,
  nichoSchema,
  nivelDetalheSchema,
  formatoExportacaoSchema,
  ConteudoAdaptadoSchema,
  FlashcardItemSchema,
  QuizItemSchema,
} from './schemas';

export type PerfilDestinatario = z.infer<typeof perfilSchema>;
export type FormatoSaida = z.infer<typeof formatoSaidaSchema>;
export type NichoSetor = z.infer<typeof nichoSchema>;
export type NivelDetalhe = z.infer<typeof nivelDetalheSchema>;
export type FormatoExportacao = z.infer<typeof formatoExportacaoSchema>;
export type AdaptacaoInput = z.infer<typeof AdaptacaoInputSchema>;
export type AdaptacaoUploadInput = z.infer<typeof AdaptacaoUploadInputSchema>;
export type AdaptacaoPacote = z.infer<typeof AdaptacaoPacoteSchema>;
export type AdaptacaoResumo = z.infer<typeof AdaptacaoResumoSchema>;
export type PaginaAdaptacoes = z.infer<typeof PaginaAdaptacoesSchema>;
export type ConteudoAdaptado = z.infer<typeof ConteudoAdaptadoSchema>;
export type FlashcardItem = z.infer<typeof FlashcardItemSchema>;
export type QuizItem = z.infer<typeof QuizItemSchema>;
export type JobResposta = z.infer<typeof JobRespostaSchema>;
export type JobStatus = JobResposta['status'];
export type EtapaJob = z.infer<typeof EtapaJobSchema>;
export type ApiProblemaErro = z.infer<typeof ApiProblemaErroSchema>;
export type ApiProblema = { erro: ApiProblemaErro };
export type OciStatus = z.infer<typeof OciStatusSchema>;
export type HealthResposta = z.infer<typeof HealthRespostaSchema>;
export type OrigemDocumento = 'upload' | 'texto';
