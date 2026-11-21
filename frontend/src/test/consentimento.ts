import { CHAVE_CONSENTIMENTO, VERSAO_CONSENTIMENTO } from '@/features/privacidade/armazenamento';

/** Parte de quem já escolheu os cookies, como a maioria dos testes de tela espera. */
export function semearConsentimento(preferencias = true): void {
  window.localStorage.setItem(
    CHAVE_CONSENTIMENTO,
    JSON.stringify({
      versao: VERSAO_CONSENTIMENTO,
      preferencias,
      decidido_em: '2026-11-21T12:00:00.000Z',
    }),
  );
}

/** Limpa o que os testes de armazenamento deixam no navegador simulado. */
export function limparArmazenamento(): void {
  window.localStorage.clear();
  window.sessionStorage.clear();
}
