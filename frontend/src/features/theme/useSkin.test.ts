import { beforeEach, describe, expect, it } from 'vitest';
import { useSkin } from './useSkin';

describe('useSkin', () => {
  beforeEach(() => {
    localStorage.clear();
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
