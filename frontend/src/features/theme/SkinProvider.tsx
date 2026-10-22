'use client';

import { useEffect } from 'react';
import { useSkin } from './useSkin';

export function SkinProvider({ children }: { children: React.ReactNode }) {
  const skin = useSkin((estado) => estado.skin);

  useEffect(() => {
    document.documentElement.dataset.skin = skin;
  }, [skin]);

  return <>{children}</>;
}
