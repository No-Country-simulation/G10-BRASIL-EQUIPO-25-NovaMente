import { beforeEach, describe, expect, it } from 'vitest';
import {
  AlunoNaoEncontrado,
  EmailJaCadastrado,
  MaterialNaoEncontrado,
  MateriaisInexistentes,
  adicionarVinculoMock,
  atualizarAlunoMock,
  criarAlunoMock,
  excluirAlunoMock,
  limparEstadoCatalogo,
  listarAlunosMock,
  listarVinculosMock,
  obterAlunoMock,
  registrarMaterialMock,
  removerVinculoMock,
  semearAlunosMock,
  substituirVinculosMock,
} from './estadoCatalogo';

const MATERIAL_A = {
  material_id: 'MATERIAL-A',
  titulo: 'Introdução à VCN',
  formato: 'Flashcards' as const,
  perfil: 'Iniciante' as const,
  visibilidade: 'publicado' as const,
};

const MATERIAL_B = {
  material_id: 'MATERIAL-B',
  titulo: 'Quiz de Redes',
  formato: 'Quiz' as const,
  perfil: 'Desenvolvedor' as const,
  visibilidade: 'rascunho' as const,
};

beforeEach(() => {
  limparEstadoCatalogo();
  registrarMaterialMock(MATERIAL_A);
  registrarMaterialMock(MATERIAL_B);
});

describe('estadoCatalogo — alunos', () => {
  it('semeia os 6 alunos da fixture, com um inativo', () => {
    semearAlunosMock();

    const pagina = listarAlunosMock({ tamanho_pagina: 50 });

    expect(pagina.total).toBe(6);
    expect(pagina.itens).toHaveLength(6);
    expect(pagina.itens.filter((aluno) => aluno.status === 'inativo')).toHaveLength(1);
    expect(new Set(pagina.itens.map((aluno) => aluno.aluno_id)).size).toBe(6);
  });

  it('criar aluno não sobrescreve nenhum aluno semeado', () => {
    semearAlunosMock();
    const idsOriginais = listarAlunosMock({ tamanho_pagina: 50 }).itens.map(
      (aluno) => aluno.aluno_id,
    );

    const criado = criarAlunoMock({ nome: 'Novo Aluno', email: 'novo@exemplo.com' });

    expect(idsOriginais).not.toContain(criado.aluno_id);
    expect(listarAlunosMock({ tamanho_pagina: 50 }).total).toBe(7);
    for (const alunoId of idsOriginais) {
      expect(obterAlunoMock(alunoId).aluno_id).toBe(alunoId);
    }
  });

  it('limparEstadoCatalogo devolve o estado ao vazio', () => {
    semearAlunosMock();
    limparEstadoCatalogo();

    expect(listarAlunosMock().total).toBe(0);
  });

  it('filtra por q e status e ordena por nome', () => {
    semearAlunosMock();
    const todos = listarAlunosMock({ tamanho_pagina: 50 }).itens;
    const alvo = todos.find((aluno) => aluno.status === 'ativo')!;

    const busca = listarAlunosMock({ q: alvo.email.toUpperCase(), status: 'ativo' });
    expect(busca.itens.map((aluno) => aluno.aluno_id)).toEqual([alvo.aluno_id]);

    const inativos = listarAlunosMock({ status: 'inativo' });
    expect(inativos.total).toBe(1);

    const nomes = listarAlunosMock({ ordenar: 'nome:asc', tamanho_pagina: 50 }).itens.map(
      (aluno) => aluno.nome,
    );
    expect(nomes).toEqual([...nomes].sort((a, b) => a.localeCompare(b, 'pt-BR')));
  });

  it('pagina e informa total de materiais do aluno', () => {
    semearAlunosMock();
    const [primeiro] = listarAlunosMock({ ordenar: 'nome:asc' }).itens;
    adicionarVinculoMock(primeiro.aluno_id, MATERIAL_A.material_id);

    const pagina = listarAlunosMock({ pagina: 2, tamanho_pagina: 2, ordenar: 'nome:asc' });
    expect(pagina.pagina).toBe(2);
    expect(pagina.total_paginas).toBe(3);
    expect(pagina.itens).toHaveLength(2);

    const atualizado = obterAlunoMock(primeiro.aluno_id);
    expect(atualizado.total_materiais).toBe(1);
  });

  it('cria aluno com nome e e-mail normalizados', () => {
    const criado = criarAlunoMock({ nome: '  Novo Aluno  ', email: '  NOVO@Exemplo.COM ' });

    expect(criado.nome).toBe('Novo Aluno');
    expect(criado.email).toBe('novo@exemplo.com');
    expect(criado.status).toBe('ativo');
    expect(criado.total_materiais).toBe(0);
    expect(criado.aluno_id).toHaveLength(26);
    expect(obterAlunoMock(criado.aluno_id).email).toBe('novo@exemplo.com');
  });

  it('recusa e-mail duplicado ignorando caixa', () => {
    criarAlunoMock({ nome: 'Ana', email: 'ana@exemplo.com' });

    expect(() => criarAlunoMock({ nome: 'Bia', email: 'ANA@EXEMPLO.COM' })).toThrow(
      EmailJaCadastrado,
    );
  });

  it('atualiza campos parciais e permite repetir o próprio e-mail', () => {
    const criado = criarAlunoMock({ nome: 'Ana', email: 'ana@exemplo.com' });

    const atualizado = atualizarAlunoMock(criado.aluno_id, {
      nome: '  Ana Souza ',
      email: ' ANA@Exemplo.COM ',
      status: 'inativo',
    });

    expect(atualizado).toMatchObject({
      nome: 'Ana Souza',
      email: 'ana@exemplo.com',
      status: 'inativo',
    });
  });

  it('recusa atualização para e-mail de outro aluno e aluno inexistente', () => {
    criarAlunoMock({ nome: 'Ana', email: 'ana@exemplo.com' });
    const bia = criarAlunoMock({ nome: 'Bia', email: 'bia@exemplo.com' });

    expect(() => atualizarAlunoMock(bia.aluno_id, { email: 'ana@exemplo.com' })).toThrow(
      EmailJaCadastrado,
    );
    expect(() => atualizarAlunoMock('NAO_EXISTE', { status: 'inativo' })).toThrow(
      AlunoNaoEncontrado,
    );
  });

  it('exclui aluno e remove os vínculos em cascata', () => {
    const criado = criarAlunoMock({ nome: 'Ana', email: 'ana@exemplo.com' });
    adicionarVinculoMock(criado.aluno_id, MATERIAL_A.material_id);

    expect(excluirAlunoMock(criado.aluno_id)).toBe(true);
    expect(() => obterAlunoMock(criado.aluno_id)).toThrow(AlunoNaoEncontrado);
    expect(() => listarVinculosMock(criado.aluno_id)).toThrow(AlunoNaoEncontrado);
    expect(() => excluirAlunoMock(criado.aluno_id)).toThrow(AlunoNaoEncontrado);
  });
});

describe('estadoCatalogo — vínculos', () => {
  it('adiciona vínculo de forma idempotente', () => {
    const criado = criarAlunoMock({ nome: 'Ana', email: 'ana@exemplo.com' });

    const primeira = adicionarVinculoMock(criado.aluno_id, MATERIAL_A.material_id);
    const segunda = adicionarVinculoMock(criado.aluno_id, MATERIAL_A.material_id);

    expect(primeira.criado).toBe(true);
    expect(segunda.criado).toBe(false);
    expect(segunda.vinculo).toEqual(primeira.vinculo);
    expect(segunda.vinculo).toMatchObject({
      material_id: MATERIAL_A.material_id,
      titulo: MATERIAL_A.titulo,
      formato: MATERIAL_A.formato,
      perfil: MATERIAL_A.perfil,
      visibilidade: MATERIAL_A.visibilidade,
    });
    expect(listarVinculosMock(criado.aluno_id).itens).toHaveLength(1);
  });

  it('diferencia aluno e material inexistentes', () => {
    const criado = criarAlunoMock({ nome: 'Ana', email: 'ana@exemplo.com' });

    expect(() => adicionarVinculoMock('NAO_EXISTE', MATERIAL_A.material_id)).toThrow(
      AlunoNaoEncontrado,
    );
    expect(() => adicionarVinculoMock(criado.aluno_id, 'NAO_EXISTE')).toThrow(
      MaterialNaoEncontrado,
    );
  });

  it('substitui, deduplica e preserva os vínculos quando algum id não existe', () => {
    const criado = criarAlunoMock({ nome: 'Ana', email: 'ana@exemplo.com' });
    adicionarVinculoMock(criado.aluno_id, MATERIAL_A.material_id);

    const substituidos = substituirVinculosMock(criado.aluno_id, [
      MATERIAL_B.material_id,
      MATERIAL_B.material_id,
      MATERIAL_A.material_id,
    ]);
    expect(substituidos.itens.map((item) => item.material_id).sort()).toEqual([
      MATERIAL_A.material_id,
      MATERIAL_B.material_id,
    ]);

    expect(() =>
      substituirVinculosMock(criado.aluno_id, [MATERIAL_A.material_id, 'NAO_EXISTE']),
    ).toThrow(MateriaisInexistentes);
    expect(listarVinculosMock(criado.aluno_id).itens).toHaveLength(2);
  });

  it('remove vínculo de forma idempotente', () => {
    const criado = criarAlunoMock({ nome: 'Ana', email: 'ana@exemplo.com' });
    adicionarVinculoMock(criado.aluno_id, MATERIAL_A.material_id);

    removerVinculoMock(criado.aluno_id, MATERIAL_A.material_id);
    removerVinculoMock(criado.aluno_id, MATERIAL_A.material_id);

    expect(listarVinculosMock(criado.aluno_id).itens).toEqual([]);
    expect(() => removerVinculoMock(criado.aluno_id, 'NAO_EXISTE')).toThrow(
      MaterialNaoEncontrado,
    );
  });
});
