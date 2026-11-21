import { beforeEach, describe, expect, it } from 'vitest';
import { SKINS } from '@/themes/registry';
import { useSkin } from './useSkin';
import { limparArmazenamento, semearConsentimento } from '@/test/consentimento';

describe('useSkin', () => {
  beforeEach(() => {
    limparArmazenamento();
    semearConsentimento();
    useSkin.setState({ skin: 'violeta', modo: 'dark' });
  });

  it('migra o estado v1, que só tinha skin, adicionando modo escuro', async () => {
    localStorage.setItem(
      'novamente.skin',
      JSON.stringify({ state: { skin: 'ciano' }, version: 1 }),
    );

    await useSkin.persist.rehydrate();

    expect(useSkin.getState().skin).toBe('ciano');
    expect(useSkin.getState().modo).toBe('dark');
  });

  it('aceita a skin neural vinda do localStorage', async () => {
    localStorage.setItem(
      'novamente.skin',
      JSON.stringify({ state: { skin: 'neural', modo: 'light' }, version: 2 }),
    );

    await useSkin.persist.rehydrate();

    expect(useSkin.getState().skin).toBe('neural');
    expect(useSkin.getState().modo).toBe('light');
  });

  it('o registro tem as três skins', () => {
    expect(Object.keys(SKINS)).toEqual(['violeta', 'ciano', 'neural']);
    expect(SKINS.neural.nome).toBe('Sinapse');
  });

  it('cai nos padrões quando skin ou modo são inválidos', async () => {
    localStorage.setItem(
      'novamente.skin',
      JSON.stringify({ state: { skin: 'roxo', modo: 'azul' }, version: 2 }),
    );

    await useSkin.persist.rehydrate();

    expect(useSkin.getState().skin).toBe('violeta');
    expect(useSkin.getState().modo).toBe('dark');
  });
});
