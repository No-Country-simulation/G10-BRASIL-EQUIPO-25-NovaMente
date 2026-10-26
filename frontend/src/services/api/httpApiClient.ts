import type { ZodType } from 'zod';
import type { NovaMenteApi, ListarAdaptacoesParams } from './NovaMenteApi';
import { montarQuery, urls } from './endpoints';
import { ErroApi, ErroContrato, ErroRede, paraProblema } from './erros';
import {
  AdaptacaoPacoteSchema,
  HealthRespostaSchema,
  JobRespostaSchema,
  OciStatusSchema,
  PaginaAdaptacoesSchema,
} from '@/types/schemas';
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
};
