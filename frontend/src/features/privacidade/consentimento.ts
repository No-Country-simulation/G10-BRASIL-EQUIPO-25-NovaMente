'use client';

import { useCallback, useMemo, useSyncExternalStore } from 'react';
import {
  analisarConsentimento,
  CHAVE_CONSENTIMENTO,
  gravarConsentimentoSalvo,
  lerConsentimentoBruto,
  promoverPreferencias,
  rebaixarPreferencias,
} from './armazenamento';

/**
 * Escolha de cookies do usuário (LGPD).
 *
 * O registro fica em `localStorage['novamente.consentimento']` e é lido com
 * `useSyncExternalStore`: no servidor e na hidratação `pronto` é falso, então o
 * banner só aparece depois que o navegador confirma que não há escolha.
 */

const ouvintes = new Set<() => void>();
let painelAberto = false;

function notificar() {
  for (const ouvinte of ouvintes) ouvinte();
}

function assinar(ouvinte: () => void) {
  ouvintes.add(ouvinte);
  if (typeof window === 'undefined') return () => ouvintes.delete(ouvinte);

  // Outra aba mudou a escolha: esta aba acompanha.
  const aoMudarArmazenamento = (evento: StorageEvent) => {
    if (evento.key === CHAVE_CONSENTIMENTO || evento.key === null) ouvinte();
  };
  window.addEventListener('storage', aoMudarArmazenamento);
  return () => {
    ouvintes.delete(ouvinte);
    window.removeEventListener('storage', aoMudarArmazenamento);
  };
}

function lerPainel() {
  return painelAberto;
}

function definirPainel(aberto: boolean) {
  if (painelAberto === aberto) return;
  painelAberto = aberto;
  notificar();
}

/** Grava a escolha e ajusta onde as preferências ficam guardadas. */
export function decidirConsentimento(preferencias: boolean): void {
  gravarConsentimentoSalvo(preferencias);
  if (preferencias) promoverPreferencias();
  else rebaixarPreferencias();
  painelAberto = false;
  notificar();
}

/** Reabre o banner (rodapé "Preferências de cookies") para quem já decidiu. */
export function reabrirPreferenciasDeCookies(): void {
  definirPainel(true);
}

export function fecharPreferenciasDeCookies(): void {
  definirPainel(false);
}

export function useConsentimento() {
  const bruto = useSyncExternalStore(assinar, lerConsentimentoBruto, () => null);
  const aberto = useSyncExternalStore(assinar, lerPainel, () => false);

  const consentimento = useMemo(() => analisarConsentimento(bruto), [bruto]);
  const decidir = useCallback((preferencias: boolean) => decidirConsentimento(preferencias), []);

  return {
    /** Falso no servidor e na hidratação. */
    pronto: bruto !== null,
    consentimento,
    /** Já escolheu (na versão atual do texto). */
    decidido: consentimento !== null,
    /** Permitiu guardar as preferências entre visitas. */
    preferencias: consentimento?.preferencias === true,
    painelAberto: aberto,
    decidir,
    reabrir: reabrirPreferenciasDeCookies,
    fechar: fecharPreferenciasDeCookies,
  };
}
