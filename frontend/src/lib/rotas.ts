export const ROTAS = {
  landing: '/',
  empresaGerar: '/empresa/gerar',
  empresaHistorico: '/empresa/historico',
  empresaResultado: (id: string) => `/empresa/resultado/${id}`,
  empresaMateriais: '/empresa/materiais',
  empresaAlunos: '/empresa/alunos',
  empresaAluno: (id: string) => `/empresa/alunos/${id}`,
  aluno: '/aluno',
  alunoMaterial: (id: string) => `/aluno/materiais/${id}`,
} as const;
