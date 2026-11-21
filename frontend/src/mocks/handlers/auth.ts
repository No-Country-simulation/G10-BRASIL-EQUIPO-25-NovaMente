import { http, HttpResponse } from 'msw';
import type { Sessao } from '@/types/novamente';
import { senhaValida } from '@/lib/senha';
import { listarAlunosMock } from '../estadoCatalogo';

/**
 * Mock do login em duas etapas (senha + código por e-mail). Desligado por
 * padrão (telas abertas, como antes do login); para ligar no navegador:
 * localStorage['novamente.mock.auth'] = '1'.
 *
 * Credenciais de demonstração:
 * - empresa: empresa@demo.com / Demo@1234
 * - aluno Ana (já tem senha): ana.silva@exemplo.com / Aluno@1234
 * - demais alunos ativos: sem senha, entram pelo primeiro acesso
 * - código de verificação: sempre 123456
 */
export const CHAVE_MOCK_AUTH = 'novamente.mock.auth';
export const CHAVE_MOCK_SESSAO = 'novamente.mock.sessao';
export const CHAVE_MOCK_SENHAS = 'novamente.mock.senhas';
export const EMPRESA_MOCK = { email: 'empresa@demo.com', senha: 'Demo@1234' };
export const ALUNO_COM_SENHA_MOCK = { email: 'ana.silva@exemplo.com', senha: 'Aluno@1234' };
export const CODIGO_MOCK = '123456';

const CODIGO_ENVIADO = {
  mensagem: 'Enviamos um código de 6 dígitos para o seu e-mail.',
  expira_em_segundos: 600,
};

let sessaoEmMemoria: Sessao | null = null;
let authLigadoEmMemoria = false;
let senhasEmMemoria: Record<string, string> = {};

function temStorage(): boolean {
  return typeof window !== 'undefined' && typeof window.localStorage !== 'undefined';
}

export function ligarAuthMock(ligado: boolean) {
  authLigadoEmMemoria = ligado;
  if (!ligado) {
    sessaoEmMemoria = null;
    senhasEmMemoria = {};
  }
}

function authLigado(): boolean {
  if (temStorage() && window.localStorage.getItem(CHAVE_MOCK_AUTH) === '1') return true;
  return authLigadoEmMemoria;
}

function lerSessao(): Sessao | null {
  if (!temStorage()) return sessaoEmMemoria;
  const bruto = window.localStorage.getItem(CHAVE_MOCK_SESSAO);
  if (!bruto) return null;
  try {
    return JSON.parse(bruto) as Sessao;
  } catch {
    return null;
  }
}

function gravarSessao(sessao: Sessao | null) {
  sessaoEmMemoria = sessao;
  if (!temStorage()) return;
  if (sessao) window.localStorage.setItem(CHAVE_MOCK_SESSAO, JSON.stringify(sessao));
  else window.localStorage.removeItem(CHAVE_MOCK_SESSAO);
}

// Senhas criadas pelos alunos no primeiro acesso (por e-mail).
function lerSenhas(): Record<string, string> {
  if (!temStorage()) return senhasEmMemoria;
  try {
    return JSON.parse(window.localStorage.getItem(CHAVE_MOCK_SENHAS) ?? '{}') as Record<string, string>;
  } catch {
    return {};
  }
}

function gravarSenha(email: string, senha: string) {
  const todas = { ...lerSenhas(), [email]: senha };
  senhasEmMemoria = todas;
  if (temStorage()) window.localStorage.setItem(CHAVE_MOCK_SENHAS, JSON.stringify(todas));
}

function senhaDoAluno(email: string): string | undefined {
  if (email === ALUNO_COM_SENHA_MOCK.email) return lerSenhas()[email] ?? ALUNO_COM_SENHA_MOCK.senha;
  return lerSenhas()[email];
}

function erro(status: number, codigo: string, mensagem: string, campos?: Record<string, string>) {
  return HttpResponse.json({ erro: { codigo, mensagem, ...(campos ? { campos } : {}) } }, { status });
}

function normalizar(email: unknown): string {
  return typeof email === 'string' ? email.trim().toLowerCase() : '';
}

function alunoAtivoPorEmail(email: string) {
  return listarAlunosMock({ tamanho_pagina: 50 }).itens.find(
    (aluno) => aluno.email.toLowerCase() === email && aluno.status === 'ativo',
  );
}

function sessaoDoAluno(email: string): Sessao | null {
  const aluno = alunoAtivoPorEmail(email);
  return aluno ? { tipo: 'aluno', aluno_id: aluno.aluno_id, nome: aluno.nome } : null;
}

export const handlersAuth = [
  http.get('*/api/v1/auth/config', () =>
    HttpResponse.json({ auth_habilitada: authLigado(), demo_habilitado: true }),
  ),

  http.get('*/api/v1/auth/eu', () => {
    const sessao = lerSessao();
    if (!authLigado() || !sessao) return erro(401, 'NAO_AUTENTICADO', 'Entre para continuar.');
    return HttpResponse.json(sessao);
  }),

  // Etapa 1 da empresa: senha correta => código por e-mail.
  http.post('*/api/v1/auth/empresa/login', async ({ request }) => {
    const corpo = (await request.json().catch(() => ({}))) as { email?: string; senha?: string };
    if (normalizar(corpo.email) !== EMPRESA_MOCK.email || corpo.senha !== EMPRESA_MOCK.senha) {
      return erro(401, 'CREDENCIAIS_INVALIDAS', 'E-mail ou senha incorretos.');
    }
    return HttpResponse.json(CODIGO_ENVIADO, { status: 202 });
  }),

  http.post('*/api/v1/auth/empresa/verificar', async ({ request }) => {
    const corpo = (await request.json().catch(() => ({}))) as { email?: string; codigo?: string };
    if (normalizar(corpo.email) !== EMPRESA_MOCK.email || corpo.codigo !== CODIGO_MOCK) {
      return erro(401, 'CODIGO_INVALIDO', 'Código inválido ou vencido.');
    }
    const sessao: Sessao = { tipo: 'empresa', email: EMPRESA_MOCK.email };
    gravarSessao(sessao);
    return HttpResponse.json(sessao);
  }),

  // Etapa 1 do aluno: aluno ativo com senha definida e senha correta => código.
  http.post('*/api/v1/auth/aluno/login', async ({ request }) => {
    const corpo = (await request.json().catch(() => ({}))) as { email?: string; senha?: string };
    const email = normalizar(corpo.email);
    const esperada = senhaDoAluno(email);
    if (!alunoAtivoPorEmail(email) || !esperada || corpo.senha !== esperada) {
      return erro(401, 'CREDENCIAIS_INVALIDAS', 'E-mail ou senha incorretos.');
    }
    return HttpResponse.json(CODIGO_ENVIADO, { status: 202 });
  }),

  http.post('*/api/v1/auth/aluno/verificar', async ({ request }) => {
    const corpo = (await request.json().catch(() => ({}))) as { email?: string; codigo?: string };
    const sessao = sessaoDoAluno(normalizar(corpo.email));
    if (!sessao || corpo.codigo !== CODIGO_MOCK) {
      return erro(401, 'CODIGO_INVALIDO', 'Código inválido ou vencido.');
    }
    gravarSessao(sessao);
    return HttpResponse.json(sessao);
  }),

  // Primeiro acesso / esqueci a senha: resposta igual exista ou não o aluno.
  http.post('*/api/v1/auth/aluno/senha/codigo', () =>
    HttpResponse.json(
      {
        mensagem: 'Se o e-mail estiver cadastrado, enviamos um código de 6 dígitos.',
        expira_em_segundos: 600,
      },
      { status: 202 },
    ),
  ),

  http.post('*/api/v1/auth/aluno/senha/definir', async ({ request }) => {
    const corpo = (await request.json().catch(() => ({}))) as {
      email?: string;
      codigo?: string;
      senha?: string;
    };
    const email = normalizar(corpo.email);
    const sessao = sessaoDoAluno(email);
    if (!sessao || corpo.codigo !== CODIGO_MOCK) {
      return erro(401, 'CODIGO_INVALIDO', 'Código inválido ou vencido.');
    }
    if (!senhaValida(corpo.senha ?? '')) {
      return erro(422, 'SENHA_FRACA', 'A senha não atende aos requisitos.', {
        senha: 'Use 8 ou mais caracteres, com maiúscula, minúscula, número e símbolo.',
      });
    }
    gravarSenha(email, corpo.senha as string);
    gravarSessao(sessao);
    return HttpResponse.json(sessao);
  }),

  http.post('*/api/v1/auth/demo', async ({ request }) => {
    const corpo = (await request.json().catch(() => ({}))) as { perfil?: string };
    if (corpo.perfil === 'empresa') {
      const sessao: Sessao = { tipo: 'empresa', email: 'demo@novamente.app', demo: true };
      gravarSessao(sessao);
      return HttpResponse.json(sessao);
    }
    if (corpo.perfil === 'aluno') {
      const primeiro = listarAlunosMock({ status: 'ativo', tamanho_pagina: 1 }).itens[0];
      if (!primeiro) return erro(404, 'ALUNO_NAO_ENCONTRADO', 'Nenhum aluno de demonstração.');
      const sessao: Sessao = {
        tipo: 'aluno',
        aluno_id: primeiro.aluno_id,
        nome: primeiro.nome,
        demo: true,
      };
      gravarSessao(sessao);
      return HttpResponse.json(sessao);
    }
    return erro(422, 'VALIDACAO', 'Perfil inválido.');
  }),

  http.post('*/api/v1/auth/sair', () => {
    gravarSessao(null);
    return new HttpResponse(null, { status: 204 });
  }),
];
