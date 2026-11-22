import { http, HttpResponse } from 'msw';
import {
  LIMITES,
  MaterialAtualizacaoSchema,
  formatoSaidaSchema,
  perfilSchema,
  visibilidadeMaterialSchema,
} from '@/types/schemas';
import type {
  FormatoSaida,
  PerfilDestinatario,
  VisibilidadeMaterial,
} from '@/types/novamente';
import {
  MaterialNaoEncontrado,
  atualizarMaterialMock,
  excluirMaterialMock,
  listarMateriaisMock,
  obterMaterialMock,
} from '../estadoCatalogo';

const ORDENACOES = ['criado_em:desc', 'criado_em:asc', 'ancoragem:desc', 'titulo:asc'] as const;

function problemas(campos: Record<string, string>) {
  return HttpResponse.json(
    { erro: { codigo: 'VALIDACAO', mensagem: 'Dados inválidos', campos } },
    { status: 422 },
  );
}

function camposDe(erro: { issues: { path: PropertyKey[]; message: string }[] }) {
  return Object.fromEntries(erro.issues.map((issue) => [issue.path.join('.'), issue.message]));
}

function materialNaoEncontrado() {
  return HttpResponse.json(
    { erro: { codigo: 'MATERIAL_NAO_ENCONTRADO', mensagem: 'Material não encontrado.' } },
    { status: 404 },
  );
}

export const handlersMateriais = [
  http.get('*/api/v1/materiais', ({ request }) => {
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

    const q = url.searchParams.get('q');
    if (q !== null && (q.length < 1 || q.length > 100)) {
      campos.q = 'Deve ter entre 1 e 100 caracteres.';
    }

    const formatoBruto = url.searchParams.get('formato');
    let formato: FormatoSaida | undefined;
    if (formatoBruto !== null) {
      const analisado = formatoSaidaSchema.safeParse(formatoBruto);
      if (analisado.success) formato = analisado.data;
      else campos.formato = 'Formato de saída desconhecido.';
    }

    const perfilBruto = url.searchParams.get('perfil');
    let perfil: PerfilDestinatario | undefined;
    if (perfilBruto !== null) {
      const analisado = perfilSchema.safeParse(perfilBruto);
      if (analisado.success) perfil = analisado.data;
      else campos.perfil = 'Perfil desconhecido.';
    }

    const visibilidadeBruta = url.searchParams.get('visibilidade');
    let visibilidade: VisibilidadeMaterial | undefined;
    if (visibilidadeBruta !== null) {
      const analisado = visibilidadeMaterialSchema.safeParse(visibilidadeBruta);
      if (analisado.success) visibilidade = analisado.data;
      else campos.visibilidade = 'Visibilidade desconhecida.';
    }

    const ordenarBruto = url.searchParams.get('ordenar') ?? 'criado_em:desc';
    if (!ORDENACOES.includes(ordenarBruto as (typeof ORDENACOES)[number])) {
      campos.ordenar = 'Ordenação desconhecida.';
    }

    if (Object.keys(campos).length > 0) return problemas(campos);

    return HttpResponse.json(
      listarMateriaisMock({
        pagina: pagina ?? 1,
        tamanho_pagina: tamanho ?? LIMITES.paginaPadrao,
        q: q ?? undefined,
        formato,
        perfil,
        visibilidade,
        ordenar: ordenarBruto as (typeof ORDENACOES)[number],
      }),
    );
  }),

  http.get('*/api/v1/materiais/:id', ({ params }) => {
    try {
      return HttpResponse.json(obterMaterialMock(String(params.id)));
    } catch (erro) {
      if (erro instanceof MaterialNaoEncontrado) return materialNaoEncontrado();
      throw erro;
    }
  }),

  http.patch('*/api/v1/materiais/:id', async ({ params, request }) => {
    const analisado = MaterialAtualizacaoSchema.safeParse(await request.json());
    if (!analisado.success) return problemas(camposDe(analisado.error));

    try {
      return HttpResponse.json(atualizarMaterialMock(String(params.id), analisado.data));
    } catch (erro) {
      if (erro instanceof MaterialNaoEncontrado) return materialNaoEncontrado();
      throw erro;
    }
  }),

  http.delete('*/api/v1/materiais/:id', ({ params }) => {
    try {
      return HttpResponse.json(excluirMaterialMock(String(params.id)));
    } catch (erro) {
      if (erro instanceof MaterialNaoEncontrado) return materialNaoEncontrado();
      throw erro;
    }
  }),
];
