'use client';

import { useEffect } from 'react';
import { useSkin } from './useSkin';

export function SkinProvider({ children }: { children: React.ReactNode }) {
  const skin = useSkin((estado) => estado.skin);
  const modo = useSkin((estado) => estado.modo);

  useEffect(() => {
    document.documentElement.dataset.skin = skin;
    document.documentElement.dataset.modo = modo;
    document.documentElement.style.colorScheme = modo;
  }, [skin, modo]);

  return <>{children}</>;
}
