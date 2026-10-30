import type {
  AdaptacaoInput,
  AdaptacaoPacote,
  AdaptacaoUploadInput,
  FormatoExportacao,
  HealthResposta,
  JobResposta,
  OciStatus,
  PaginaAdaptacoes,
} from '@/types/novamente';

export interface ListarAdaptacoesParams {
  pagina?: number;
  tamanho_pagina?: number;
  formato?: string;
  perfil?: string;
  q?: string;
  ordenar?: 'criado_em:desc' | 'criado_em:asc' | 'ancoragem:desc';
}

export interface NovaMenteApi {
  criarPorTexto(input: AdaptacaoInput): Promise<JobResposta>;
  criarPorArquivo(input: AdaptacaoUploadInput): Promise<JobResposta>;
  obterJob(jobId: string): Promise<JobResposta>;
  cancelarJob(jobId: string): Promise<JobResposta>;
  listar(params?: ListarAdaptacoesParams): Promise<PaginaAdaptacoes>;
  obter(adaptacaoId: string): Promise<AdaptacaoPacote>;
  baixarJson(adaptacaoId: string): Promise<Blob>;
  exportar(adaptacaoId: string, formato: FormatoExportacao): Promise<Blob>;
  statusOci(): Promise<OciStatus>;
  health(): Promise<HealthResposta>;
}
