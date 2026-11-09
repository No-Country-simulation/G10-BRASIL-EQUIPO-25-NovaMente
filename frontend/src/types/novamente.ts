import type { z } from 'zod';
import type {
  AdaptacaoInputSchema,
  AdaptacaoPacoteSchema,
  AdaptacaoResumoSchema,
  AdaptacaoUploadInputSchema,
  AlunoAtualizacaoSchema,
  AlunoCriacaoSchema,
  AlunoResumoSchema,
  ApiProblemaErroSchema,
  AtualizarVinculosInputSchema,
  EtapaJobSchema,
  HealthRespostaSchema,
  JobRespostaSchema,
  MaterialAtualizacaoSchema,
  MaterialDetalheSchema,
  MaterialResumoSchema,
  OciStatusSchema,
  PaginaAdaptacoesSchema,
  PaginaAlunosSchema,
  PaginaMateriaisSchema,
  RemocaoMaterialRespostaSchema,
  VinculoMaterialSchema,
  VinculosAlunoSchema,
  perfilSchema,
  formatoSaidaSchema,
  nichoSchema,
  nivelDetalheSchema,
  formatoExportacaoSchema,
  ConteudoAdaptadoSchema,
  FlashcardItemSchema,
  QuizItemSchema,
  statusAlunoSchema,
  visibilidadeMaterialSchema,
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

export type StatusAluno = z.infer<typeof statusAlunoSchema>;
export type AlunoCriacao = z.infer<typeof AlunoCriacaoSchema>;
export type AlunoAtualizacao = z.infer<typeof AlunoAtualizacaoSchema>;
export type AlunoResumo = z.infer<typeof AlunoResumoSchema>;
export type PaginaAlunos = z.infer<typeof PaginaAlunosSchema>;
export type VisibilidadeMaterial = z.infer<typeof visibilidadeMaterialSchema>;
export type VinculoMaterial = z.infer<typeof VinculoMaterialSchema>;
export type VinculosAluno = z.infer<typeof VinculosAlunoSchema>;
export type AtualizarVinculosInput = z.infer<typeof AtualizarVinculosInputSchema>;
export type MaterialAtualizacao = z.infer<typeof MaterialAtualizacaoSchema>;
export type MaterialResumo = z.infer<typeof MaterialResumoSchema>;
export type MaterialDetalhe = z.infer<typeof MaterialDetalheSchema>;
export type PaginaMateriais = z.infer<typeof PaginaMateriaisSchema>;
export type RemocaoMaterialResposta = z.infer<typeof RemocaoMaterialRespostaSchema>;
