import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

/**
 * Injeta o X-API-Key da empresa nas chamadas ao backend que exigem credencial.
 *
 * A chave vem de `API_KEY_EMPRESA` (variável só de servidor, nunca `NEXT_PUBLIC_*`)
 * e é anexada aqui, no servidor do Next, antes do rewrite para a API. O navegador
 * não a vê. Sem a variável, o proxy não faz nada (dev local e modo mock).
 *
 * Limite conhecido: isto protege a API contra acesso direto à porta do backend,
 * não as telas da empresa. Quem alcança o front alcança as rotas via rewrite;
 * separar empresa e aluno exige login, decisão em aberto no time.
 */

const CABECALHO_CHAVE = 'X-API-Key';

/** Rotas da empresa no backend (as do aluno, em /aluno/*, não levam credencial). */
export function exigeChaveEmpresa(metodo: string, caminho: string): boolean {
  const m = metodo.toUpperCase();
  if (/^\/api\/v1\/(alunos|materiais)(\/|$)/.test(caminho)) return true;
  if (/^\/api\/v1\/adaptacoes(\/|$)/.test(caminho)) return m === 'POST';
  if (/^\/api\/v1\/jobs\//.test(caminho)) return m === 'DELETE';
  return false;
}

export function proxy(request: NextRequest) {
  const chave = process.env.API_KEY_EMPRESA?.trim();
  if (!chave || !exigeChaveEmpresa(request.method, request.nextUrl.pathname)) {
    return NextResponse.next();
  }

  const cabecalhos = new Headers(request.headers);
  cabecalhos.set(CABECALHO_CHAVE, chave);
  return NextResponse.next({ request: { headers: cabecalhos } });
}

export const config = {
  matcher: '/api/v1/:path*',
};
