import type {
  AdaptacaoPacote,
  AlunoAtualizacao,
  AlunoCriacao,
  AlunoResumo,
  FormatoSaida,
  IdentificacaoAlunoItem,
  ItemCatalogoAluno,
  MaterialAtualizacao,
  MaterialResumo,
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
import { LIMITES } from '@/types/schemas';
import alunosFixture from './fixtures/alunos.json';
import flashcardsFixture from './fixtures/flashcards-vcn-iniciante.json';
import materiaisFixture from './fixtures/materiais.json';
import quizFixture from './fixtures/quiz-vcn-desenvolvedor.json';
import resumoFixture from './fixtures/resumo-vcn-gestor.json';
import tutorialFixture from './fixtures/tutorial-vcn-lider.json';

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

export interface FiltrosMateriaisMock {
  pagina?: number;
  tamanho_pagina?: number;
  q?: string;
  formato?: FormatoSaida;
  perfil?: PerfilDestinatario;
  visibilidade?: VisibilidadeMaterial;
  ordenar?: 'criado_em:desc' | 'criado_em:asc' | 'ancoragem:desc' | 'titulo:asc';
}

export interface FiltrosCatalogoAlunoMock {
  pagina?: number;
  tamanho_pagina?: number;
  q?: string;
  formato?: FormatoSaida;
  perfil?: PerfilDestinatario;
  ordenar?: 'criado_em:desc' | 'titulo:asc';
}

export class AlunoNaoEncontrado extends Error {
  constructor() {
    super('Aluno não encontrado.');
    this.name = 'AlunoNaoEncontrado';
  }
}

export class AlunoInativo extends Error {
  constructor() {
    super('Aluno inativo.');
    this.name = 'AlunoInativo';
  }
}

export class MaterialNaoEncontrado extends Error {
  constructor() {
    super('Material não encontrado.');
    this.name = 'MaterialNaoEncontrado';
  }
}

export class MaterialNaoDisponivel extends Error {
  constructor() {
    super('Material não disponível.');
    this.name = 'MaterialNaoDisponivel';
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
const catalogo = new Map<string, MaterialResumo>();
const pacotes = new Map<string, AdaptacaoPacote>();

const PACOTES_POR_ADAPTACAO: Record<string, AdaptacaoPacote> = {
  [flashcardsFixture.adaptacao_id]: flashcardsFixture as unknown as AdaptacaoPacote,
  [quizFixture.adaptacao_id]: quizFixture as unknown as AdaptacaoPacote,
  [tutorialFixture.adaptacao_id]: tutorialFixture as unknown as AdaptacaoPacote,
  [resumoFixture.adaptacao_id]: resumoFixture as unknown as AdaptacaoPacote,
};

const VINCULO_SEMEADO_EM = '2026-10-24T09:00:00Z';

let sequencia = 0;

function agoraIso() {
  return new Date().toISOString();
}

function novoIdAluno() {
  // Os ids da fixture usam a mesma faixa; avança até um id livre para que um
  // POST nunca sobrescreva um aluno semeado.
  let id: string;
  do {
    sequencia += 1;
    id = `01JALUNO${String(sequencia).padStart(18, '0')}`;
  } while (alunos.has(id));
  return id;
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

function exigirAlunoAtivo(alunoId: string): AlunoResumo {
  const aluno = exigirAluno(alunoId);
  if (aluno.status !== 'ativo') throw new AlunoInativo();
  return aluno;
}

function exigirMaterial(materialId: string): MaterialMock {
  const material = materiais.get(materialId);
  if (!material) throw new MaterialNaoEncontrado();
  return material;
}

function exigirMaterialDoCatalogo(materialId: string): MaterialResumo {
  const material = catalogo.get(materialId);
  if (!material) throw new MaterialNaoEncontrado();
  return material;
}

function materialParaVinculo(material: MaterialResumo): MaterialMock {
  return {
    material_id: material.material_id,
    titulo: material.titulo,
    formato: material.formato,
    perfil: material.perfil,
    visibilidade: material.visibilidade,
  };
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

/**
 * Semeia vínculos do primeiro aluno ativo com os materiais da fixture.
 *
 * Só roda quando alunos e catálogo estão completos e ainda não há vínculos,
 * para não interferir em testes que montam um estado mínimo próprio.
 */
function semearVinculosIniciaisMock() {
  if (vinculos.size > 0) return;
  if (alunos.size === 0 || catalogo.size !== materiaisFixture.length) return;

  const primeiroAtivo = [...alunos.values()]
    .filter((aluno) => aluno.status === 'ativo')
    .sort(
      (a, b) => a.nome.localeCompare(b.nome, 'pt-BR') || a.aluno_id.localeCompare(b.aluno_id),
    )[0];
  if (!primeiroAtivo) return;

  vinculos.set(
    primeiroAtivo.aluno_id,
    new Map([...catalogo.keys()].sort().map((materialId) => [materialId, VINCULO_SEMEADO_EM])),
  );
}

/** Recarrega os 6 alunos de demonstração da fixture, com um inativo. */
export function semearAlunosMock() {
  alunos.clear();
  vinculos.clear();
  for (const base of alunosFixture as unknown as AlunoResumo[]) {
    const aluno = structuredClone(base);
    alunos.set(aluno.aluno_id, { ...aluno, total_materiais: 0 });
  }
  semearVinculosIniciaisMock();
}

/** Recarrega os materiais da fixture e os pacotes das fixtures de adaptação. */
export function semearMateriaisMock() {
  materiais.clear();
  catalogo.clear();
  pacotes.clear();
  for (const base of materiaisFixture as unknown as MaterialResumo[]) {
    const material = structuredClone(base);
    catalogo.set(material.material_id, material);
    materiais.set(material.material_id, materialParaVinculo(material));
    const pacote = PACOTES_POR_ADAPTACAO[material.adaptacao_id];
    if (pacote) pacotes.set(material.material_id, structuredClone(pacote));
  }
  semearVinculosIniciaisMock();
}

/** Zera todo o catálogo mock (alunos, vínculos e materiais). */
export function limparEstadoCatalogo() {
  alunos.clear();
  vinculos.clear();
  materiais.clear();
  catalogo.clear();
  pacotes.clear();
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

export function listarMateriaisMock(filtros: FiltrosMateriaisMock = {}): PaginaMateriais {
  const pagina = filtros.pagina ?? 1;
  const tamanho = filtros.tamanho_pagina ?? LIMITES.paginaPadrao;
  const termo = (filtros.q ?? '').trim().toLowerCase();
  const ordenar = filtros.ordenar ?? 'criado_em:desc';

  const filtrados = [...catalogo.values()]
    .filter(
      (material) =>
        !termo ||
        material.titulo.toLowerCase().includes(termo) ||
        material.documento_titulo.toLowerCase().includes(termo),
    )
    .filter((material) => (filtros.formato ? material.formato === filtros.formato : true))
    .filter((material) => (filtros.perfil ? material.perfil === filtros.perfil : true))
    .filter((material) =>
      filtros.visibilidade ? material.visibilidade === filtros.visibilidade : true,
    )
    .sort((a, b) => {
      const porId = a.material_id.localeCompare(b.material_id);
      if (ordenar === 'ancoragem:desc') {
        return b.ancoragem_fonte_score - a.ancoragem_fonte_score || porId;
      }
      if (ordenar === 'titulo:asc') {
        return a.titulo.localeCompare(b.titulo, 'pt-BR') || porId;
      }
      const porData = Date.parse(a.criado_em) - Date.parse(b.criado_em);
      return (ordenar === 'criado_em:asc' ? porData : -porData) || porId;
    });

  const total = filtrados.length;
  const inicio = (pagina - 1) * tamanho;

  return {
    itens: filtrados.slice(inicio, inicio + tamanho).map((material) => structuredClone(material)),
    pagina,
    tamanho_pagina: tamanho,
    total,
    total_paginas: total ? Math.ceil(total / tamanho) : 0,
  };
}

function itemCatalogoDe(material: MaterialResumo): ItemCatalogoAluno {
  return {
    material_id: material.material_id,
    titulo: material.titulo,
    documento_titulo: material.documento_titulo,
    formato: material.formato,
    perfil: material.perfil,
    nivel: material.nivel,
    tempo_estimado_estudo_minutos: material.tempo_estimado_estudo_minutos,
    criado_em: material.criado_em,
    conceitos_chave: (pacotes.get(material.material_id)?.metadados.conceitos_chave ?? []).slice(
      0,
      6,
    ),
  };
}

/** Identificação da área do aluno: apenas ativos, por nome, sem e-mail. */
export function listarIdentificacaoAlunoMock(): IdentificacaoAlunoItem[] {
  return [...alunos.values()]
    .filter((aluno) => aluno.status === 'ativo')
    .sort(
      (a, b) => a.nome.localeCompare(b.nome, 'pt-BR') || a.aluno_id.localeCompare(b.aluno_id),
    )
    .map((aluno) => ({ aluno_id: aluno.aluno_id, nome: aluno.nome }));
}

/** Catálogo do aluno: somente publicados e vinculados ao aluno ativo. */
export function listarCatalogoAlunoMock(
  alunoId: string,
  filtros: FiltrosCatalogoAlunoMock = {},
): PaginaCatalogoAluno {
  exigirAlunoAtivo(alunoId);

  const pagina = filtros.pagina ?? 1;
  const tamanho = filtros.tamanho_pagina ?? LIMITES.paginaPadrao;
  const termo = (filtros.q ?? '').trim().toLowerCase();
  const ordenar = filtros.ordenar ?? 'criado_em:desc';
  const vinculados = vinculos.get(alunoId) ?? new Map<string, string>();

  const filtrados = [...vinculados.keys()]
    .flatMap((materialId) => {
      const material = catalogo.get(materialId);
      return material && material.visibilidade === 'publicado' ? [material] : [];
    })
    .filter(
      (material) =>
        !termo ||
        material.titulo.toLowerCase().includes(termo) ||
        material.documento_titulo.toLowerCase().includes(termo),
    )
    .filter((material) => (filtros.formato ? material.formato === filtros.formato : true))
    .filter((material) => (filtros.perfil ? material.perfil === filtros.perfil : true))
    .sort((a, b) => {
      const porId = a.material_id.localeCompare(b.material_id);
      if (ordenar === 'titulo:asc') {
        return a.titulo.localeCompare(b.titulo, 'pt-BR') || porId;
      }
      return Date.parse(b.criado_em) - Date.parse(a.criado_em) || porId;
    });

  const total = filtrados.length;
  const inicio = (pagina - 1) * tamanho;

  return {
    itens: filtrados.slice(inicio, inicio + tamanho).map(itemCatalogoDe),
    pagina,
    tamanho_pagina: tamanho,
    total,
    total_paginas: total ? Math.ceil(total / tamanho) : 0,
  };
}

/** Detalhe do aluno: aluno ativo, material publicado e vinculado. */
export function obterMaterialAlunoMock(
  alunoId: string,
  materialId: string,
): { material: MaterialResumo; pacote: AdaptacaoPacote } {
  exigirAlunoAtivo(alunoId);

  const material = catalogo.get(materialId);
  const vinculado = vinculos.get(alunoId)?.has(materialId) ?? false;
  if (!material || material.visibilidade !== 'publicado' || !vinculado) {
    throw new MaterialNaoDisponivel();
  }

  return obterMaterialMock(materialId);
}

export function obterMaterialMock(materialId: string): {
  material: MaterialResumo;
  pacote: AdaptacaoPacote;
} {
  const material = exigirMaterialDoCatalogo(materialId);
  const pacote = pacotes.get(materialId);
  if (!pacote) throw new MaterialNaoEncontrado();
  return { material: structuredClone(material), pacote: structuredClone(pacote) };
}

export function atualizarMaterialMock(
  materialId: string,
  dados: MaterialAtualizacao,
): MaterialResumo {
  const material = exigirMaterialDoCatalogo(materialId);

  if (dados.titulo !== undefined) material.titulo = dados.titulo.trim();
  if (dados.visibilidade !== undefined) material.visibilidade = dados.visibilidade;
  material.atualizado_em = agoraIso();

  // O vínculo guarda uma cópia do título/visibilidade; mantém os painéis
  // de alunos coerentes sem obrigar a recarregar o catálogo.
  const vinculo = materiais.get(materialId);
  if (vinculo) {
    vinculo.titulo = material.titulo;
    vinculo.visibilidade = material.visibilidade;
  }

  return structuredClone(material);
}

export function excluirMaterialMock(materialId: string): RemocaoMaterialResposta {
  exigirMaterialDoCatalogo(materialId);
  const pacote = pacotes.get(materialId);

  catalogo.delete(materialId);
  materiais.delete(materialId);
  pacotes.delete(materialId);
  for (const doAluno of vinculos.values()) doAluno.delete(materialId);

  const ociRemovido = pacote?.armazenamento_oci.status_upload === 'concluido';
  return {
    material_id: materialId,
    removido: true,
    oci_removido: ociRemovido,
    ...(ociRemovido
      ? {}
      : { aviso: 'Objeto OCI indisponível; a remoção local foi concluída.' }),
  };
}

// A demo abre com o catálogo de alunos e materiais preenchido.
semearAlunosMock();
semearMateriaisMock();
