import { beforeEach, describe, expect, it } from 'vitest';
import { limparArmazenamento, semearConsentimento } from '@/test/consentimento';
import {
  analisarConsentimento,
  CHAVE_CONSENTIMENTO,
  gravarConsentimentoSalvo,
  gravarPreferencia,
  lerConsentimentoSalvo,
  lerPreferencia,
  podeGuardarPreferencias,
  promoverPreferencias,
  rebaixarPreferencias,
  removerPreferencia,
  VERSAO_CONSENTIMENTO,
} from './armazenamento';

beforeEach(() => limparArmazenamento());

describe('escolha de cookies', () => {
  it('sem registro, não há escolha e as preferências não podem ser guardadas', () => {
    expect(lerConsentimentoSalvo()).toBeNull();
    expect(podeGuardarPreferencias()).toBe(false);
  });

  it('grava a escolha com a versão e a data', () => {
    gravarConsentimentoSalvo(true);

    const salvo = lerConsentimentoSalvo();
    expect(salvo).toMatchObject({ versao: VERSAO_CONSENTIMENTO, preferencias: true });
    expect(Number.isNaN(Date.parse(salvo!.decidido_em))).toBe(false);
    expect(podeGuardarPreferencias()).toBe(true);
  });

  it('descarta registro corrompido, de outra versão ou incompleto', () => {
    expect(analisarConsentimento('{')).toBeNull();
    expect(analisarConsentimento('[]')).toBeNull();
    expect(
      analisarConsentimento(
        JSON.stringify({ versao: VERSAO_CONSENTIMENTO + 1, preferencias: true, decidido_em: 'x' }),
      ),
    ).toBeNull();
    expect(
      analisarConsentimento(JSON.stringify({ versao: VERSAO_CONSENTIMENTO, preferencias: 'sim' })),
    ).toBeNull();
    window.localStorage.setItem(CHAVE_CONSENTIMENTO, '{"versao":0}');
    expect(lerConsentimentoSalvo()).toBeNull();
  });
});

describe('preferências (tema e tour)', () => {
  it('sem consentimento, ficam só na sessão do navegador', () => {
    gravarPreferencia('novamente.tour', 'a');

    expect(window.localStorage.getItem('novamente.tour')).toBeNull();
    expect(window.sessionStorage.getItem('novamente.tour')).toBe('a');
    expect(lerPreferencia('novamente.tour')).toBe('a');
  });

  it('com consentimento, duram entre visitas e saem da sessão', () => {
    semearConsentimento(true);
    window.sessionStorage.setItem('novamente.skin', 'velho');

    gravarPreferencia('novamente.skin', 'novo');

    expect(window.localStorage.getItem('novamente.skin')).toBe('novo');
    expect(window.sessionStorage.getItem('novamente.skin')).toBeNull();
  });

  it('com a escolha "somente necessários", segue só na sessão', () => {
    semearConsentimento(false);

    gravarPreferencia('novamente.skin', 'x');

    expect(window.localStorage.getItem('novamente.skin')).toBeNull();
    expect(window.sessionStorage.getItem('novamente.skin')).toBe('x');
  });

  it('aceitar promove o que estava na sessão, inclusive o tour por conta', () => {
    gravarPreferencia('novamente.skin', 's');
    gravarPreferencia('novamente.tour:empresa:a@demo.com', 't');
    window.sessionStorage.setItem('outra.chave', 'fica');

    semearConsentimento(true);
    promoverPreferencias();

    expect(window.localStorage.getItem('novamente.skin')).toBe('s');
    expect(window.localStorage.getItem('novamente.tour:empresa:a@demo.com')).toBe('t');
    expect(window.sessionStorage.getItem('novamente.skin')).toBeNull();
    expect(window.sessionStorage.getItem('outra.chave')).toBe('fica');
  });

  it('recusar ou revogar apaga o que estava salvo e mantém só na sessão', () => {
    semearConsentimento(true);
    gravarPreferencia('novamente.skin', 's');
    gravarPreferencia('novamente.tour', 't');
    window.localStorage.setItem('novamente.aluno', '{"aluno_id":"A1"}');

    semearConsentimento(false);
    rebaixarPreferencias();

    expect(window.localStorage.getItem('novamente.skin')).toBeNull();
    expect(window.localStorage.getItem('novamente.tour')).toBeNull();
    expect(window.sessionStorage.getItem('novamente.skin')).toBe('s');
    expect(window.sessionStorage.getItem('novamente.tour')).toBe('t');
    // Dado necessário não é tocado.
    expect(window.localStorage.getItem('novamente.aluno')).toBe('{"aluno_id":"A1"}');
    expect(window.localStorage.getItem(CHAVE_CONSENTIMENTO)).not.toBeNull();
  });

  it('removerPreferencia limpa as duas áreas', () => {
    semearConsentimento(true);
    gravarPreferencia('novamente.tour', 't');
    window.sessionStorage.setItem('novamente.tour', 't');

    removerPreferencia('novamente.tour');

    expect(lerPreferencia('novamente.tour')).toBeNull();
  });
});
