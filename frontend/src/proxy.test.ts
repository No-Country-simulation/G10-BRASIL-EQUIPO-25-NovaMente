// @vitest-environment node
import { afterEach, describe, expect, it, vi } from 'vitest';
import { NextRequest } from 'next/server';
import { exigeChaveEmpresa, proxy } from './proxy';

afterEach(() => vi.unstubAllEnvs());

function chamar(metodo: string, caminho: string, cabecalhos: Record<string, string> = {}) {
  return proxy(new NextRequest(`http://localhost:3000${caminho}`, { method: metodo, headers: cabecalhos }));
}

// O Next sinaliza os cabeçalhos de requisição alterados com este prefixo na resposta.
const injetado = (resposta: Response, nome: string) =>
  resposta.headers.get(`x-middleware-request-${nome.toLowerCase()}`);

describe('exigeChaveEmpresa', () => {
  it.each([
    ['GET', '/api/v1/alunos'],
    ['POST', '/api/v1/alunos'],
    ['PATCH', '/api/v1/alunos/A1'],
    ['PUT', '/api/v1/alunos/A1/materiais'],
    ['GET', '/api/v1/materiais'],
    ['DELETE', '/api/v1/materiais/M1'],
    ['POST', '/api/v1/materiais/M1/chat'],
    ['POST', '/api/v1/adaptacoes'],
    ['POST', '/api/v1/adaptacoes/upload'],
    ['DELETE', '/api/v1/jobs/J1'],
  ])('exige a chave em %s %s', (metodo, caminho) => {
    expect(exigeChaveEmpresa(metodo, caminho)).toBe(true);
  });

  it.each([
    ['GET', '/api/v1/health'],
    ['GET', '/api/v1/oci/status'],
    ['GET', '/api/v1/chat/modelos'],
    ['GET', '/api/v1/jobs/J1'],
    ['GET', '/api/v1/adaptacoes'],
    ['GET', '/api/v1/adaptacoes/A1/download'],
    ['GET', '/api/v1/aluno/identificacao'],
    ['GET', '/api/v1/aluno/materiais'],
    ['POST', '/api/v1/aluno/materiais/M1/chat'],
    ['GET', '/api/v1/alunos-extra'],
  ])('não exige a chave em %s %s', (metodo, caminho) => {
    expect(exigeChaveEmpresa(metodo, caminho)).toBe(false);
  });
});

describe('proxy', () => {
  it('anexa X-API-Key nas rotas da empresa quando a variável existe', () => {
    vi.stubEnv('API_KEY_EMPRESA', 'chave-de-teste');

    const resposta = chamar('GET', '/api/v1/materiais');

    expect(injetado(resposta, 'x-api-key')).toBe('chave-de-teste');
  });

  it('substitui um X-API-Key enviado pelo navegador', () => {
    vi.stubEnv('API_KEY_EMPRESA', 'chave-de-teste');

    const resposta = chamar('POST', '/api/v1/materiais/M1/chat', { 'X-API-Key': 'forjada' });

    expect(injetado(resposta, 'x-api-key')).toBe('chave-de-teste');
  });

  it('não mexe nas rotas do aluno nem nas públicas', () => {
    vi.stubEnv('API_KEY_EMPRESA', 'chave-de-teste');

    expect(injetado(chamar('GET', '/api/v1/aluno/materiais'), 'x-api-key')).toBeNull();
    expect(injetado(chamar('GET', '/api/v1/health'), 'x-api-key')).toBeNull();
  });

  it('não faz nada sem a variável (ou com ela vazia)', () => {
    vi.stubEnv('API_KEY_EMPRESA', '');

    expect(injetado(chamar('GET', '/api/v1/materiais'), 'x-api-key')).toBeNull();
  });

  it('nunca devolve a chave ao navegador', () => {
    vi.stubEnv('API_KEY_EMPRESA', 'chave-de-teste');

    const resposta = chamar('GET', '/api/v1/materiais');

    const visivel = [...resposta.headers.entries()].filter(([nome]) => !nome.startsWith('x-middleware-'));
    expect(JSON.stringify(visivel)).not.toContain('chave-de-teste');
  });
});
