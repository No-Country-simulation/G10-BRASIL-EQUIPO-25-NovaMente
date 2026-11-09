import { http, HttpResponse } from 'msw';
import {
  AlunoAtualizacaoSchema,
  AlunoCriacaoSchema,
  AtualizarVinculosInputSchema,
  LIMITES,
  statusAlunoSchema,
} from '@/types/schemas';
import type { StatusAluno } from '@/types/novamente';
import {
  AlunoNaoEncontrado,
  EmailJaCadastrado,
  MaterialNaoEncontrado,
  MateriaisInexistentes,
  adicionarVinculoMock,
  atualizarAlunoMock,
  criarAlunoMock,
  excluirAlunoMock,
  listarAlunosMock,
  listarVinculosMock,
  obterAlunoMock,
  removerVinculoMock,
  substituirVinculosMock,
} from '../estadoCatalogo';

const ORDENACOES = ['nome:asc', 'nome:desc', 'criado_em:desc'] as const;

function problemas(campos: Record<string, string>) {
  return HttpResponse.json(
    { erro: { codigo: 'VALIDACAO', mensagem: 'Dados inválidos', campos } },
    { status: 422 },
  );
}

function camposDe(erro: { issues: { path: PropertyKey[]; message: string }[] }) {
  return Object.fromEntries(erro.issues.map((issue) => [issue.path.join('.'), issue.message]));
}

function alunoNaoEncontrado() {
  return HttpResponse.json(
    { erro: { codigo: 'ALUNO_NAO_ENCONTRADO', mensagem: 'Aluno não encontrado.' } },
    { status: 404 },
  );
}

function materialNaoEncontrado() {
  return HttpResponse.json(
    { erro: { codigo: 'MATERIAL_NAO_ENCONTRADO', mensagem: 'Material não encontrado.' } },
    { status: 404 },
  );
}

function emailDuplicado() {
  return HttpResponse.json(
    {
      erro: {
        codigo: 'EMAIL_JA_CADASTRADO',
        mensagem: 'E-mail já cadastrado.',
        campos: { email: 'E-mail já cadastrado.' },
      },
    },
    { status: 409 },
  );
}

function materiaisInexistentes(erro: MateriaisInexistentes) {
  return HttpResponse.json(
    {
      erro: {
        codigo: 'VALIDACAO',
        mensagem: 'Dados de entrada inválidos.',
        campos: { material_ids: erro.message },
      },
    },
    { status: 422 },
  );
}

export const handlersAlunos = [
  http.get('*/api/v1/alunos', ({ request }) => {
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

    const statusBruto = url.searchParams.get('status');
    let status: StatusAluno | undefined;
    if (statusBruto !== null) {
      const analisado = statusAlunoSchema.safeParse(statusBruto);
      if (analisado.success) status = analisado.data;
      else campos.status = 'Status desconhecido.';
    }

    const ordenarBruto = url.searchParams.get('ordenar') ?? 'nome:asc';
    if (!ORDENACOES.includes(ordenarBruto as (typeof ORDENACOES)[number])) {
      campos.ordenar = 'Ordenação desconhecida.';
    }

    if (Object.keys(campos).length > 0) return problemas(campos);

    return HttpResponse.json(
      listarAlunosMock({
        pagina: pagina ?? 1,
        tamanho_pagina: tamanho ?? LIMITES.paginaPadrao,
        q: q ?? undefined,
        status,
        ordenar: ordenarBruto as (typeof ORDENACOES)[number],
      }),
    );
  }),

  http.post('*/api/v1/alunos', async ({ request }) => {
    const analisado = AlunoCriacaoSchema.safeParse(await request.json());
    if (!analisado.success) return problemas(camposDe(analisado.error));

    try {
      return HttpResponse.json(criarAlunoMock(analisado.data), { status: 201 });
    } catch (erro) {
      if (erro instanceof EmailJaCadastrado) return emailDuplicado();
      throw erro;
    }
  }),

  http.get('*/api/v1/alunos/:id/materiais', ({ params }) => {
    try {
      return HttpResponse.json(listarVinculosMock(String(params.id)));
    } catch (erro) {
      if (erro instanceof AlunoNaoEncontrado) return alunoNaoEncontrado();
      throw erro;
    }
  }),

  http.put('*/api/v1/alunos/:id/materiais', async ({ params, request }) => {
    const analisado = AtualizarVinculosInputSchema.safeParse(await request.json());
    if (!analisado.success) return problemas(camposDe(analisado.error));

    try {
      return HttpResponse.json(
        substituirVinculosMock(String(params.id), analisado.data.material_ids),
      );
    } catch (erro) {
      if (erro instanceof AlunoNaoEncontrado) return alunoNaoEncontrado();
      if (erro instanceof MateriaisInexistentes) return materiaisInexistentes(erro);
      throw erro;
    }
  }),

  http.post('*/api/v1/alunos/:id/materiais/:materialId', ({ params }) => {
    try {
      const { vinculo, criado } = adicionarVinculoMock(
        String(params.id),
        String(params.materialId),
      );
      return HttpResponse.json(vinculo, { status: criado ? 201 : 200 });
    } catch (erro) {
      if (erro instanceof AlunoNaoEncontrado) return alunoNaoEncontrado();
      if (erro instanceof MaterialNaoEncontrado) return materialNaoEncontrado();
      throw erro;
    }
  }),

  http.delete('*/api/v1/alunos/:id/materiais/:materialId', ({ params }) => {
    try {
      removerVinculoMock(String(params.id), String(params.materialId));
      return new HttpResponse(null, { status: 204 });
    } catch (erro) {
      if (erro instanceof AlunoNaoEncontrado) return alunoNaoEncontrado();
      if (erro instanceof MaterialNaoEncontrado) return materialNaoEncontrado();
      throw erro;
    }
  }),

  http.get('*/api/v1/alunos/:id', ({ params }) => {
    try {
      return HttpResponse.json(obterAlunoMock(String(params.id)));
    } catch (erro) {
      if (erro instanceof AlunoNaoEncontrado) return alunoNaoEncontrado();
      throw erro;
    }
  }),

  http.patch('*/api/v1/alunos/:id', async ({ params, request }) => {
    const analisado = AlunoAtualizacaoSchema.safeParse(await request.json());
    if (!analisado.success) return problemas(camposDe(analisado.error));

    try {
      return HttpResponse.json(atualizarAlunoMock(String(params.id), analisado.data));
    } catch (erro) {
      if (erro instanceof AlunoNaoEncontrado) return alunoNaoEncontrado();
      if (erro instanceof EmailJaCadastrado) return emailDuplicado();
      throw erro;
    }
  }),

  http.delete('*/api/v1/alunos/:id', ({ params }) => {
    try {
      excluirAlunoMock(String(params.id));
      return new HttpResponse(null, { status: 204 });
    } catch (erro) {
      if (erro instanceof AlunoNaoEncontrado) return alunoNaoEncontrado();
      throw erro;
    }
  }),
];
