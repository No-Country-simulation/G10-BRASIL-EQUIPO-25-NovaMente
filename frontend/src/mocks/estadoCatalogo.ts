import type {
  AlunoAtualizacao,
  AlunoCriacao,
  AlunoResumo,
  FormatoSaida,
  PaginaAlunos,
  PerfilDestinatario,
  StatusAluno,
  VinculoMaterial,
  VinculosAluno,
} from '@/types/novamente';
import { LIMITES } from '@/types/schemas';
import alunosFixture from './fixtures/alunos.json';

/** Dados mínimos de um material necessários para montar um vínculo. */
export interface MaterialMock {
  material_id: string;
  titulo: string;
  formato: FormatoSaida;
  perfil: PerfilDestinatario;
  visibilidade: 'rascunho' | 'publicado';
}

export interface FiltrosAlunosMock {
  pagina?: number;
  tamanho_pagina?: number;
  q?: string;
  status?: StatusAluno;
  ordenar?: 'nome:asc' | 'nome:desc' | 'criado_em:desc';
}

export class AlunoNaoEncontrado extends Error {
  constructor() {
    super('Aluno não encontrado.');
    this.name = 'AlunoNaoEncontrado';
  }
}

export class MaterialNaoEncontrado extends Error {
  constructor() {
    super('Material não encontrado.');
    this.name = 'MaterialNaoEncontrado';
  }
}

export class EmailJaCadastrado extends Error {
  constructor() {
    super('E-mail já cadastrado.');
    this.name = 'EmailJaCadastrado';
  }
}

export class MateriaisInexistentes extends Error {
  constructor(public readonly materialIds: string[]) {
    super(`Materiais não encontrados: ${materialIds.join(', ')}.`);
    this.name = 'MateriaisInexistentes';
  }
}

const alunos = new Map<string, AlunoResumo>();
const vinculos = new Map<string, Map<string, string>>();
const materiais = new Map<string, MaterialMock>();

let sequencia = 0;

function agoraIso() {
  return new Date().toISOString();
}

function novoIdAluno() {
  sequencia += 1;
  return `01JALUNO${String(sequencia).padStart(18, '0')}`;
}

function normalizarEmail(email: string) {
  return email.trim().toLowerCase();
}

function totalMateriais(alunoId: string) {
  return vinculos.get(alunoId)?.size ?? 0;
}

function comTotal(aluno: AlunoResumo): AlunoResumo {
  return { ...aluno, total_materiais: totalMateriais(aluno.aluno_id) };
}

function exigirAluno(alunoId: string): AlunoResumo {
  const aluno = alunos.get(alunoId);
  if (!aluno) throw new AlunoNaoEncontrado();
  return aluno;
}

function exigirMaterial(materialId: string): MaterialMock {
  const material = materiais.get(materialId);
  if (!material) throw new MaterialNaoEncontrado();
  return material;
}

function emailEmUso(email: string, ignorarAlunoId?: string) {
  return [...alunos.values()].some(
    (aluno) => aluno.aluno_id !== ignorarAlunoId && aluno.email.toLowerCase() === email,
  );
}

function vinculoDe(material: MaterialMock, vinculadoEm: string): VinculoMaterial {
  return {
    material_id: material.material_id,
    titulo: material.titulo,
    formato: material.formato,
    perfil: material.perfil,
    visibilidade: material.visibilidade,
    vinculado_em: vinculadoEm,
  };
}

/** Recarrega os 6 alunos de demonstração da fixture, com um inativo. */
export function semearAlunosMock() {
  alunos.clear();
  vinculos.clear();
  for (const base of alunosFixture as unknown as AlunoResumo[]) {
    const aluno = structuredClone(base);
    alunos.set(aluno.aluno_id, { ...aluno, total_materiais: 0 });
  }
}

/** Zera todo o catálogo mock (alunos, vínculos e materiais). */
export function limparEstadoCatalogo() {
  alunos.clear();
  vinculos.clear();
  materiais.clear();
  sequencia = 0;
}

export function registrarMaterialMock(material: MaterialMock) {
  materiais.set(material.material_id, structuredClone(material));
}

export function listarAlunosMock(filtros: FiltrosAlunosMock = {}): PaginaAlunos {
  const pagina = filtros.pagina ?? 1;
  const tamanho = filtros.tamanho_pagina ?? LIMITES.paginaPadrao;
  const termo = (filtros.q ?? '').trim().toLowerCase();
  const ordenar = filtros.ordenar ?? 'nome:asc';

  const filtrados = [...alunos.values()]
    .filter(
      (aluno) =>
        !termo ||
        aluno.nome.toLowerCase().includes(termo) ||
        aluno.email.toLowerCase().includes(termo),
    )
    .filter((aluno) => (filtros.status ? aluno.status === filtros.status : true))
    .sort((a, b) => {
      if (ordenar === 'criado_em:desc') {
        return Date.parse(b.criado_em) - Date.parse(a.criado_em) || a.aluno_id.localeCompare(b.aluno_id);
      }
      const porNome = a.nome.localeCompare(b.nome, 'pt-BR');
      const comparacao = porNome || a.aluno_id.localeCompare(b.aluno_id);
      return ordenar === 'nome:desc' ? -comparacao : comparacao;
    });

  const total = filtrados.length;
  const inicio = (pagina - 1) * tamanho;

  return {
    itens: filtrados.slice(inicio, inicio + tamanho).map(comTotal),
    pagina,
    tamanho_pagina: tamanho,
    total,
    total_paginas: total ? Math.ceil(total / tamanho) : 0,
  };
}

export function criarAlunoMock(dados: AlunoCriacao): AlunoResumo {
  const nome = dados.nome.trim();
  const email = normalizarEmail(dados.email);
  if (emailEmUso(email)) throw new EmailJaCadastrado();

  const agora = agoraIso();
  const aluno: AlunoResumo = {
    aluno_id: novoIdAluno(),
    nome,
    email,
    status: dados.status ?? 'ativo',
    total_materiais: 0,
    criado_em: agora,
    atualizado_em: agora,
  };
  alunos.set(aluno.aluno_id, aluno);
  return structuredClone(aluno);
}

export function obterAlunoMock(alunoId: string): AlunoResumo {
  return structuredClone(comTotal(exigirAluno(alunoId)));
}

export function atualizarAlunoMock(
  alunoId: string,
  dados: AlunoAtualizacao,
): AlunoResumo {
  const aluno = exigirAluno(alunoId);

  if (dados.email !== undefined) {
    const email = normalizarEmail(dados.email);
    if (emailEmUso(email, alunoId)) throw new EmailJaCadastrado();
    aluno.email = email;
  }
  if (dados.nome !== undefined) aluno.nome = dados.nome.trim();
  if (dados.status !== undefined) aluno.status = dados.status;

  aluno.atualizado_em = agoraIso();
  return structuredClone(comTotal(aluno));
}

export function excluirAlunoMock(alunoId: string): boolean {
  exigirAluno(alunoId);
  alunos.delete(alunoId);
  vinculos.delete(alunoId);
  return true;
}

export function listarVinculosMock(alunoId: string): VinculosAluno {
  exigirAluno(alunoId);

  const itens = [...(vinculos.get(alunoId)?.entries() ?? [])]
    .sort((a, b) => b[1].localeCompare(a[1]) || a[0].localeCompare(b[0]))
    .flatMap(([materialId, vinculadoEm]) => {
      const material = materiais.get(materialId);
      return material ? [vinculoDe(material, vinculadoEm)] : [];
    });

  return { aluno_id: alunoId, itens };
}

export function substituirVinculosMock(
  alunoId: string,
  materialIds: string[],
): VinculosAluno {
  exigirAluno(alunoId);

  const unicos = [...new Set(materialIds)];
  const faltando = unicos.filter((materialId) => !materiais.has(materialId)).sort();
  if (faltando.length > 0) throw new MateriaisInexistentes(faltando);

  const agora = agoraIso();
  vinculos.set(
    alunoId,
    new Map(unicos.map((materialId) => [materialId, agora])),
  );
  return listarVinculosMock(alunoId);
}

export function adicionarVinculoMock(
  alunoId: string,
  materialId: string,
): { vinculo: VinculoMaterial; criado: boolean } {
  exigirAluno(alunoId);
  const material = exigirMaterial(materialId);

  const doAluno = vinculos.get(alunoId) ?? new Map<string, string>();
  const existente = doAluno.get(materialId);
  if (existente !== undefined) {
    return { vinculo: vinculoDe(material, existente), criado: false };
  }

  const agora = agoraIso();
  doAluno.set(materialId, agora);
  vinculos.set(alunoId, doAluno);
  return { vinculo: vinculoDe(material, agora), criado: true };
}

export function removerVinculoMock(alunoId: string, materialId: string): void {
  exigirAluno(alunoId);
  exigirMaterial(materialId);
  vinculos.get(alunoId)?.delete(materialId);
}

// A demo abre com o catálogo de alunos preenchido.
semearAlunosMock();
