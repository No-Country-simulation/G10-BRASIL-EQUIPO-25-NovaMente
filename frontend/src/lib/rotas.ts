export const ROTAS = {
  landing: '/',
  entrar: '/entrar',
  privacidade: '/privacidade',
  entrarComo: (perfil: 'empresa' | 'aluno', proximo?: string) => {
    const busca = new URLSearchParams({ perfil });
    if (proximo) busca.set('proximo', proximo);
    return `/entrar?${busca.toString()}`;
  },
  empresaGerar: '/empresa/gerar',
  empresaHistorico: '/empresa/historico',
  empresaResultado: (id: string) => `/empresa/resultado/${id}`,
  empresaMateriais: '/empresa/materiais',
  empresaAlunos: '/empresa/alunos',
  empresaAluno: (id: string) => `/empresa/alunos/${id}`,
  aluno: '/aluno',
  alunoMaterial: (id: string) => `/aluno/materiais/${id}`,
} as const;
