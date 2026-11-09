import type { ZodType } from 'zod';
import type {
  ListarAdaptacoesParams,
  ListarMateriaisParams,
  NovaMenteApi,
} from './NovaMenteApi';
import { montarQuery, urls } from './endpoints';
import { ErroApi, ErroContrato, ErroRede, paraProblema } from './erros';
import {
  AdaptacaoPacoteSchema,
  AlunoResumoSchema,
  HealthRespostaSchema,
  JobRespostaSchema,
  MaterialDetalheSchema,
  MaterialResumoSchema,
  OciStatusSchema,
  PaginaAdaptacoesSchema,
  PaginaAlunosSchema,
  PaginaMateriaisSchema,
  RemocaoMaterialRespostaSchema,
  VinculoMaterialSchema,
  VinculosAlunoSchema,
} from '@/types/schemas';
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
  MaterialAtualizacao,
  MaterialDetalhe,
  MaterialResumo,
  OciStatus,
  PaginaAdaptacoes,
  PaginaAlunos,
  PaginaMateriais,
  RemocaoMaterialResposta,
  StatusAluno,
  VinculoMaterial,
  VinculosAluno,
} from '@/types/novamente';

async function lerCorpo(resposta: Response): Promise<unknown> {
  try {
    return await resposta.json();
  } catch {
    return null;
  }
}

function descreverProblemaDeContrato(erro: { issues: { path: PropertyKey[]; message: string }[] }): string {
  return erro.issues
    .map((issue) => `${issue.path.map(String).join('.') || '(raiz)'}: ${issue.message}`)
    .join('; ');
}

function validar<T>(schema: ZodType<T>, dados: unknown): T {
  const analisado = schema.safeParse(dados);
  if (!analisado.success) throw new ErroContrato(descreverProblemaDeContrato(analisado.error));
  return analisado.data;
}

async function pedir<T>(caminho: string, schema: ZodType<T>, init?: RequestInit): Promise<T> {
  let resposta: Response;
  try {
    resposta = await fetch(caminho, init);
  } catch {
    throw new ErroRede();
  }
  if (!resposta.ok) {
    throw new ErroApi(paraProblema(resposta.status, await lerCorpo(resposta)), resposta.status);
  }
  const corpo = await lerCorpo(resposta);
  return validar(schema, corpo);
}

async function pedirSemCorpo(caminho: string, init?: RequestInit): Promise<void> {
  let resposta: Response;
  try {
    resposta = await fetch(caminho, init);
  } catch {
    throw new ErroRede();
  }
  if (!resposta.ok) {
    throw new ErroApi(paraProblema(resposta.status, await lerCorpo(resposta)), resposta.status);
  }
}

interface CorpoAluno {
  nome?: string;
  email?: string;
  status?: StatusAluno;
}

// O backend também normaliza, mas enviar o corpo já limpo mantém o mock e o
// servidor alinhados e evita duplicidade por caixa/espaço.
function normalizarAluno(input: CorpoAluno): CorpoAluno {
  return {
    ...(input.nome !== undefined ? { nome: input.nome.trim() } : {}),
    ...(input.email !== undefined ? { email: input.email.trim().toLowerCase() } : {}),
    ...(input.status !== undefined ? { status: input.status } : {}),
  };
}

async function pedirArquivo(caminho: string): Promise<Blob> {
  let resposta: Response;
  try {
    resposta = await fetch(caminho);
  } catch {
    throw new ErroRede();
  }
  if (!resposta.ok) {
    throw new ErroApi(paraProblema(resposta.status, await lerCorpo(resposta)), resposta.status);
  }
  return resposta.blob();
}

function formDataDe(input: AdaptacaoUploadInput): FormData {
  const form = new FormData();
  form.set('arquivo', input.arquivo);
  form.set('documento_titulo', input.documento_titulo);
  form.set('perfil_destinatario', input.perfil_destinatario);
  form.set('formato_saida', input.formato_saida);
  form.set('nicho_setor', input.nicho_setor);
  form.set('nivel_detalhe', input.nivel_detalhe);
  return form;
}

export const httpApiClient: NovaMenteApi = {
  criarPorTexto: (input: AdaptacaoInput) =>
    pedir<JobResposta>(urls.adaptacoes, JobRespostaSchema, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(input),
    }),

  criarPorArquivo: (input) =>
    pedir<JobResposta>(urls.upload, JobRespostaSchema, { method: 'POST', body: formDataDe(input) }),

  obterJob: (jobId) => pedir<JobResposta>(urls.job(jobId), JobRespostaSchema),

  cancelarJob: (jobId) => pedir<JobResposta>(urls.job(jobId), JobRespostaSchema, { method: 'DELETE' }),

  listar: (params: ListarAdaptacoesParams = {}) =>
    pedir<PaginaAdaptacoes>(
      `${urls.adaptacoes}${montarQuery({
        pagina: params.pagina,
        tamanho_pagina: params.tamanho_pagina,
        formato: params.formato,
        perfil: params.perfil,
        q: params.q,
        ordenar: params.ordenar,
      })}`,
      PaginaAdaptacoesSchema,
    ),

  obter: (adaptacaoId) => pedir<AdaptacaoPacote>(urls.adaptacao(adaptacaoId), AdaptacaoPacoteSchema),

  baixarJson: (adaptacaoId) => pedirArquivo(urls.download(adaptacaoId)),

  exportar: (adaptacaoId, formato: FormatoExportacao) =>
    pedirArquivo(`${urls.exportacao(adaptacaoId)}${montarQuery({ formato })}`),

  statusOci: () => pedir<OciStatus>(urls.ociStatus, OciStatusSchema),

  health: () => pedir<HealthResposta>(urls.health, HealthRespostaSchema),

  listarAlunos: (params = {}) =>
    pedir<PaginaAlunos>(
      `${urls.alunos}${montarQuery({
        pagina: params.pagina,
        tamanho_pagina: params.tamanho_pagina,
        q: params.q,
        status: params.status,
        ordenar: params.ordenar,
      })}`,
      PaginaAlunosSchema,
    ),

  criarAluno: (input: AlunoCriacao) =>
    pedir<AlunoResumo>(urls.alunos, AlunoResumoSchema, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(normalizarAluno(input)),
    }),

  obterAluno: (alunoId) => pedir<AlunoResumo>(urls.aluno(alunoId), AlunoResumoSchema),

  atualizarAluno: (alunoId, input: AlunoAtualizacao) =>
    pedir<AlunoResumo>(urls.aluno(alunoId), AlunoResumoSchema, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(normalizarAluno(input)),
    }),

  excluirAluno: (alunoId) => pedirSemCorpo(urls.aluno(alunoId), { method: 'DELETE' }),

  listarVinculos: (alunoId) =>
    pedir<VinculosAluno>(urls.alunoMateriais(alunoId), VinculosAlunoSchema),

  substituirVinculos: (alunoId, input: AtualizarVinculosInput) =>
    pedir<VinculosAluno>(urls.alunoMateriais(alunoId), VinculosAlunoSchema, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(input),
    }),

  adicionarVinculo: (alunoId, materialId) =>
    pedir<VinculoMaterial>(urls.alunoVinculo(alunoId, materialId), VinculoMaterialSchema, {
      method: 'POST',
    }),

  removerVinculo: (alunoId, materialId) =>
    pedirSemCorpo(urls.alunoVinculo(alunoId, materialId), { method: 'DELETE' }),

  listarMateriais: (params: ListarMateriaisParams = {}) =>
    pedir<PaginaMateriais>(
      `${urls.materiais}${montarQuery({
        pagina: params.pagina,
        tamanho_pagina: params.tamanho_pagina,
        q: params.q,
        formato: params.formato,
        perfil: params.perfil,
        visibilidade: params.visibilidade,
        ordenar: params.ordenar,
      })}`,
      PaginaMateriaisSchema,
    ),

  obterMaterial: (materialId) =>
    pedir<MaterialDetalhe>(urls.material(materialId), MaterialDetalheSchema),

  atualizarMaterial: (materialId, input: MaterialAtualizacao) =>
    pedir<MaterialResumo>(urls.material(materialId), MaterialResumoSchema, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(input),
    }),

  excluirMaterial: (materialId) =>
    pedir<RemocaoMaterialResposta>(urls.material(materialId), RemocaoMaterialRespostaSchema, {
      method: 'DELETE',
    }),
};
