import type {
  AdaptacaoInput,
  AdaptacaoPacote,
  AdaptacaoUploadInput,
  AlunoAtualizacao,
  AlunoCriacao,
  AlunoResumo,
  AtualizarVinculosInput,
  FormatoExportacao,
  FormatoSaida,
  HealthResposta,
  IdentificacaoAlunoItem,
  JobResposta,
  MaterialAtualizacao,
  MaterialDetalhe,
  MaterialResumo,
  OciStatus,
  PaginaAdaptacoes,
  PaginaAlunos,
  PaginaCatalogoAluno,
  PaginaMateriais,
  PerfilDestinatario,
  RemocaoMaterialResposta,
  StatusAluno,
  VinculoMaterial,
  VinculosAluno,
  VisibilidadeMaterial,
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

export interface ListarMateriaisParams {
  pagina?: number;
  tamanho_pagina?: number;
  q?: string;
  formato?: FormatoSaida;
  perfil?: PerfilDestinatario;
  visibilidade?: VisibilidadeMaterial;
  ordenar?: 'criado_em:desc' | 'criado_em:asc' | 'ancoragem:desc' | 'titulo:asc';
}

export interface ListarCatalogoAlunoParams {
  pagina?: number;
  tamanho_pagina?: number;
  q?: string;
  formato?: FormatoSaida;
  perfil?: PerfilDestinatario;
  ordenar?: 'criado_em:desc' | 'titulo:asc';
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

  listarMateriais(params?: ListarMateriaisParams): Promise<PaginaMateriais>;
  obterMaterial(materialId: string): Promise<MaterialDetalhe>;
  atualizarMaterial(materialId: string, input: MaterialAtualizacao): Promise<MaterialResumo>;
  excluirMaterial(materialId: string): Promise<RemocaoMaterialResposta>;

  listarIdentificacaoAluno(): Promise<IdentificacaoAlunoItem[]>;
  listarCatalogoAluno(
    alunoId: string,
    params?: ListarCatalogoAlunoParams,
  ): Promise<PaginaCatalogoAluno>;
  obterMaterialAluno(alunoId: string, materialId: string): Promise<MaterialDetalhe>;
}
