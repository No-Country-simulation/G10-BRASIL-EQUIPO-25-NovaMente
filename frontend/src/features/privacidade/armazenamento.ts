/**
 * Armazenamento do navegador sob a LGPD.
 *
 * Duas classes de dados ficam no navegador:
 *
 * - **Necessários** (sessão, identidade do aluno logado e a própria escolha de
 *   cookies): não dependem de consentimento e não passam por aqui.
 * - **Preferências** (tema e tour guiado): só vão para o `localStorage`, que
 *   dura entre visitas, com o consentimento do usuário. Sem ele, ficam no
 *   `sessionStorage` e somem quando o navegador é fechado.
 *
 * Tudo aqui é seguro no servidor (sem `window`) e com o armazenamento
 * bloqueado: nesses casos as funções devolvem `null` ou não fazem nada.
 */

export const CHAVE_CONSENTIMENTO = 'novamente.consentimento';

/**
 * Versão do texto de privacidade e das categorias. Ao subir este número, quem
 * já decidiu volta a ver o banner e escolhe de novo.
 */
export const VERSAO_CONSENTIMENTO = 1;

/** Chaves (e prefixos `chave:conta`) tratadas como "preferências". */
export const CHAVES_DE_PREFERENCIAS = ['novamente.skin', 'novamente.tour'] as const;

export interface ConsentimentoSalvo {
  versao: number;
  preferencias: boolean;
  decidido_em: string;
}

function persistente(): Storage | null {
  try {
    return typeof window === 'undefined' ? null : window.localStorage;
  } catch {
    return null;
  }
}

function temporario(): Storage | null {
  try {
    return typeof window === 'undefined' ? null : window.sessionStorage;
  } catch {
    return null;
  }
}

function ehPreferencia(chave: string): boolean {
  return CHAVES_DE_PREFERENCIAS.some((base) => chave === base || chave.startsWith(`${base}:`));
}

// ── Escolha do usuário ─────────────────────────────────────────────────────

/** Texto gravado, `''` sem escolha e `null` onde não há navegador. */
export function lerConsentimentoBruto(): string | null {
  const armazenamento = persistente();
  if (!armazenamento) return typeof window === 'undefined' ? null : '';
  try {
    return armazenamento.getItem(CHAVE_CONSENTIMENTO) ?? '';
  } catch {
    return '';
  }
}

/** Escolha válida e da versão atual; qualquer outra coisa vale como "sem escolha". */
export function analisarConsentimento(bruto: string | null): ConsentimentoSalvo | null {
  if (!bruto) return null;
  try {
    const dados = JSON.parse(bruto) as Partial<ConsentimentoSalvo> | null;
    if (
      dados &&
      dados.versao === VERSAO_CONSENTIMENTO &&
      typeof dados.preferencias === 'boolean' &&
      typeof dados.decidido_em === 'string'
    ) {
      return {
        versao: dados.versao,
        preferencias: dados.preferencias,
        decidido_em: dados.decidido_em,
      };
    }
  } catch {
    // JSON corrompido: o usuário decide de novo.
  }
  return null;
}

export function lerConsentimentoSalvo(): ConsentimentoSalvo | null {
  return analisarConsentimento(lerConsentimentoBruto());
}

export function gravarConsentimentoSalvo(preferencias: boolean): void {
  const registro: ConsentimentoSalvo = {
    versao: VERSAO_CONSENTIMENTO,
    preferencias,
    decidido_em: new Date().toISOString(),
  };
  try {
    persistente()?.setItem(CHAVE_CONSENTIMENTO, JSON.stringify(registro));
  } catch {
    // Armazenamento bloqueado ou cheio: a escolha vale só até recarregar.
  }
}

export function podeGuardarPreferencias(): boolean {
  return lerConsentimentoSalvo()?.preferencias === true;
}

// ── Preferências (tema, tour) ──────────────────────────────────────────────

export function lerPreferencia(chave: string): string | null {
  try {
    return persistente()?.getItem(chave) ?? temporario()?.getItem(chave) ?? null;
  } catch {
    return null;
  }
}

export function gravarPreferencia(chave: string, valor: string): void {
  try {
    if (podeGuardarPreferencias()) {
      persistente()?.setItem(chave, valor);
      temporario()?.removeItem(chave);
    } else {
      temporario()?.setItem(chave, valor);
      persistente()?.removeItem(chave);
    }
  } catch {
    // Sem armazenamento: a preferência vale só nesta tela.
  }
}

export function removerPreferencia(chave: string): void {
  try {
    persistente()?.removeItem(chave);
    temporario()?.removeItem(chave);
  } catch {
    // nada a fazer
  }
}

function chavesDe(armazenamento: Storage | null): string[] {
  if (!armazenamento) return [];
  const chaves: string[] = [];
  for (let indice = 0; indice < armazenamento.length; indice += 1) {
    const chave = armazenamento.key(indice);
    if (chave && ehPreferencia(chave)) chaves.push(chave);
  }
  return chaves;
}

/** Aceitou as preferências: o que estava só na sessão passa a durar. */
export function promoverPreferencias(): void {
  const origem = temporario();
  const destino = persistente();
  if (!origem || !destino) return;
  try {
    for (const chave of chavesDe(origem)) {
      const valor = origem.getItem(chave);
      if (valor !== null) destino.setItem(chave, valor);
      origem.removeItem(chave);
    }
  } catch {
    // mantém o que já foi copiado
  }
}

/**
 * Recusou ou revogou: nada de preferências guardadas entre visitas. O que
 * está em uso continua valendo até fechar o navegador.
 */
export function rebaixarPreferencias(): void {
  const origem = persistente();
  const destino = temporario();
  if (!origem) return;
  try {
    for (const chave of chavesDe(origem)) {
      const valor = origem.getItem(chave);
      if (valor !== null) destino?.setItem(chave, valor);
      origem.removeItem(chave);
    }
  } catch {
    // mantém o que já foi movido
  }
}

/** Adaptador para o `persist` do zustand (tema). */
export const armazenamentoDePreferencias = {
  getItem: (nome: string) => lerPreferencia(nome),
  setItem: (nome: string, valor: string) => gravarPreferencia(nome, valor),
  removeItem: (nome: string) => removerPreferencia(nome),
};
