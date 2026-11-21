// `cor` repete o --accent de cada skin em tokens.css (amostra do seletor compacto).
// `selo` é opcional e aparece ao lado do nome no seletor, a partir de sm.
export const SKINS = {
  violeta: { id: 'violeta', nome: 'Violeta', cor: '#8b5cf6' },
  ciano: { id: 'ciano', nome: 'Ciano', cor: '#22d3ee' },
  neural: { id: 'neural', nome: 'Sinapse', cor: '#76b900', selo: 'Especial' },
} as const;

export type SkinId = keyof typeof SKINS;

export const SKIN_PADRAO: SkinId = 'violeta';

export function seloDaSkin(id: SkinId): string | undefined {
  const skin = SKINS[id];
  return 'selo' in skin ? skin.selo : undefined;
}

export const MODOS = {
  dark: { id: 'dark', nome: 'Escuro' },
  light: { id: 'light', nome: 'Claro' },
} as const;

export type Modo = keyof typeof MODOS;

export const MODO_PADRAO: Modo = 'dark';
