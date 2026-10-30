import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { SKIN_PADRAO, type SkinId } from '@/themes/registry';

interface SkinState {
  skin: SkinId;
  setSkin: (skin: SkinId) => void;
}

export const useSkin = create<SkinState>()(
  persist(
    (set) => ({
      skin: SKIN_PADRAO,
      setSkin: (skin) => set({ skin }),
    }),
    { name: 'novamente.skin', version: 1 },
  ),
);
