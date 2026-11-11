import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import {
  MODO_PADRAO,
  type Modo,
  SKIN_PADRAO,
  SKINS,
  type SkinId,
} from '@/themes/registry';

interface SkinState {
  skin: SkinId;
  modo: Modo;
  setSkin: (skin: SkinId) => void;
  setModo: (modo: Modo) => void;
  alternarModo: () => void;
}

const SKINS_VALIDAS = new Set<string>(Object.keys(SKINS));

function normalizarTema(valor: unknown): { skin: SkinId; modo: Modo } {
  const estado = (valor ?? {}) as { skin?: unknown; modo?: unknown };
  return {
    skin:
      typeof estado.skin === 'string' && SKINS_VALIDAS.has(estado.skin)
        ? (estado.skin as SkinId)
        : SKIN_PADRAO,
    modo:
      estado.modo === 'dark' || estado.modo === 'light' ? estado.modo : MODO_PADRAO,
  };
}

export const useSkin = create<SkinState>()(
  persist(
    (set) => ({
      skin: SKIN_PADRAO,
      modo: MODO_PADRAO,
      setSkin: (skin) => set({ skin }),
      setModo: (modo) => set({ modo }),
      alternarModo: () =>
        set((estado) => ({ modo: estado.modo === 'dark' ? 'light' : 'dark' })),
    }),
    {
      name: 'novamente.skin',
      version: 2,
      // v1 guardava só { skin }; adiciona o modo padrão sem perder a preferência.
      migrate: (persistido) => ({ ...(persistido as object), ...normalizarTema(persistido) }),
      merge: (persistido, atual) => ({ ...atual, ...normalizarTema(persistido) }),
    },
  ),
);

export { normalizarTema };
