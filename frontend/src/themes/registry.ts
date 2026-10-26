export const SKINS = {
  violeta: { id: 'violeta', nome: 'Violeta' },
  ciano: { id: 'ciano', nome: 'Ciano' },
} as const;

export type SkinId = keyof typeof SKINS;

export const SKIN_PADRAO: SkinId = 'violeta';
