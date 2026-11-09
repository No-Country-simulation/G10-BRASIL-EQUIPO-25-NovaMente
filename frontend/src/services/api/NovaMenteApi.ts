import type {
  AdaptacaoInput,
  AdaptacaoPacote,
  AdaptacaoUploadInput,
  AlunoAtualizacao,
  AlunoCriacao,
  AlunoResumo,
  AtualizarVinculosInput,
  FormatoExportacao,
  HealthResposta,
  JobResposta,
  OciStatus,
  PaginaAdaptacoes,
  PaginaAlunos,
  StatusAluno,
  VinculoMaterial,
  VinculosAluno,
} from '@/types/novamente';

export interface ListarAdaptacoesParams {
  pagina?: number;
  tamanho_pagina?: number;
  formato?: string;
  perfil?: string;
  q?: string;
  ordenar?: 'criado_em:desc' | 'criado_em:asc' | 'ancoragem:desc';
}

export interface ListarAlunosParams {
  pagina?: number;
  tamanho_pagina?: number;
  q?: string;
  status?: StatusAluno;
  ordenar?: 'nome:asc' | 'nome:desc' | 'criado_em:desc';
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

  listarAlunos(params?: ListarAlunosParams): Promise<PaginaAlunos>;
  criarAluno(input: AlunoCriacao): Promise<AlunoResumo>;
  obterAluno(alunoId: string): Promise<AlunoResumo>;
  atualizarAluno(alunoId: string, input: AlunoAtualizacao): Promise<AlunoResumo>;
  excluirAluno(alunoId: string): Promise<void>;

  listarVinculos(alunoId: string): Promise<VinculosAluno>;
  substituirVinculos(alunoId: string, input: AtualizarVinculosInput): Promise<VinculosAluno>;
  adicionarVinculo(alunoId: string, materialId: string): Promise<VinculoMaterial>;
  removerVinculo(alunoId: string, materialId: string): Promise<void>;
}
