'use client';

import dynamic from 'next/dynamic';
import { useEffect, useSyncExternalStore } from 'react';
import { useSkin } from './useSkin';

// O fundo animado só é baixado e executado com a skin Neural ativa.
const NeuralBackground = dynamic(() => import('./neural/NeuralBackground'), { ssr: false });

const semInscricao = () => () => {};

export function SkinProvider({ children }: { children: React.ReactNode }) {
  const skin = useSkin((estado) => estado.skin);
  const modo = useSkin((estado) => estado.modo);
  // Falso no servidor e na hidratação: a primeira pintura do cliente bate com o HTML.
  const noCliente = useSyncExternalStore(
    semInscricao,
    () => true,
    () => false,
  );

  useEffect(() => {
    document.documentElement.dataset.skin = skin;
    document.documentElement.dataset.modo = modo;
    document.documentElement.style.colorScheme = modo;
  }, [skin, modo]);

  return (
    <>
      {noCliente && skin === 'neural' ? <NeuralBackground /> : null}
      {children}
    </>
  );
}
