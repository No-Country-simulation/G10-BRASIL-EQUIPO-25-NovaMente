import { http, HttpResponse } from 'msw';
import {
  LIMITES,
  formatoSaidaSchema,
  perfilSchema,
} from '@/types/schemas';
import type { FormatoSaida, PerfilDestinatario } from '@/types/novamente';
import {
  AlunoInativo,
  AlunoNaoEncontrado,
  MaterialNaoDisponivel,
  listarCatalogoAlunoMock,
  listarIdentificacaoAlunoMock,
  obterMaterialAlunoMock,
} from '../estadoCatalogo';

const ORDENACOES = ['criado_em:desc', 'titulo:asc'] as const;

function problemas(campos: Record<string, string>) {
  return HttpResponse.json(
    { erro: { codigo: 'VALIDACAO', mensagem: 'Dados inválidos', campos } },
    { status: 422 },
  );
}

function alunoNaoEncontrado() {
  return HttpResponse.json(
    { erro: { codigo: 'ALUNO_NAO_ENCONTRADO', mensagem: 'Aluno não encontrado.' } },
    { status: 404 },
  );
}

function alunoInativo() {
  return HttpResponse.json(
    { erro: { codigo: 'ALUNO_INATIVO', mensagem: 'Aluno inativo.' } },
    { status: 403 },
  );
}

function materialNaoDisponivel() {
  return HttpResponse.json(
    { erro: { codigo: 'MATERIAL_NAO_DISPONIVEL', mensagem: 'Material não disponível.' } },
    { status: 404 },
  );
}

function inteiro(
  bruto: string | null,
  padrao: number,
  minimo: number,
  maximo: number,
): number | null {
  if (bruto === null || bruto === '') return padrao;
  if (!/^\d+$/.test(bruto)) return null;
  const numero = Number(bruto);
  return numero >= minimo && numero <= maximo ? numero : null;
}

export const handlersAluno = [
  http.get('*/api/v1/aluno/identificacao', () =>
    HttpResponse.json({ itens: listarIdentificacaoAlunoMock() }),
  ),

  http.get('*/api/v1/aluno/materiais', ({ request }) => {
    const url = new URL(request.url);
    const campos: Record<string, string> = {};

    const alunoId = url.searchParams.get('aluno_id');
    if (alunoId === null || alunoId === '') {
      campos.aluno_id = 'Informe o aluno.';
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

    const ordenarBruto = url.searchParams.get('ordenar') ?? 'criado_em:desc';
    if (!ORDENACOES.includes(ordenarBruto as (typeof ORDENACOES)[number])) {
      campos.ordenar = 'Ordenação desconhecida.';
    }

    if (Object.keys(campos).length > 0) return problemas(campos);

    try {
      return HttpResponse.json(
        listarCatalogoAlunoMock(alunoId ?? '', {
          pagina: pagina ?? 1,
          tamanho_pagina: tamanho ?? LIMITES.paginaPadrao,
          q: q ?? undefined,
          formato,
          perfil,
          ordenar: ordenarBruto as (typeof ORDENACOES)[number],
        }),
      );
    } catch (erro) {
      if (erro instanceof AlunoNaoEncontrado) return alunoNaoEncontrado();
      if (erro instanceof AlunoInativo) return alunoInativo();
      throw erro;
    }
  }),

  http.get('*/api/v1/aluno/materiais/:materialId', ({ params, request }) => {
    const url = new URL(request.url);
    const alunoId = url.searchParams.get('aluno_id');
    if (alunoId === null || alunoId === '') {
      return problemas({ aluno_id: 'Informe o aluno.' });
    }

    try {
      return HttpResponse.json(obterMaterialAlunoMock(alunoId, String(params.materialId)));
    } catch (erro) {
      if (erro instanceof AlunoNaoEncontrado) return alunoNaoEncontrado();
      if (erro instanceof AlunoInativo) return alunoInativo();
      if (erro instanceof MaterialNaoDisponivel) return materialNaoDisponivel();
      throw erro;
    }
  }),
];
