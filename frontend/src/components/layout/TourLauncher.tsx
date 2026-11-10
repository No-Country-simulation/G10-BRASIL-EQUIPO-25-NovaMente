'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { usePathname } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { M } from '@/lib/mensagens';
import { ROTAS } from '@/lib/rotas';
import {
  deveAutoIniciar,
  marcarConcluido,
  useTour,
  type OrigemTour,
} from '@/features/tour/useTour';

export interface TourLauncherProps {
  origem: OrigemTour;
  /** Injeta o início nos testes e no auto-start. */
  iniciar?: (origem: OrigemTour) => Promise<void>;
}

export function TourLauncher({ origem, iniciar }: TourLauncherProps) {
  const pathname = usePathname();
  const { iniciarTour } = useTour();
  const executar = iniciar ?? iniciarTour;
  const [iniciando, setIniciando] = useState(false);
  const jaIniciado = useRef(false);

  useEffect(() => {
    if (jaIniciado.current) return;

    const forcado =
      typeof window !== 'undefined' &&
      new URLSearchParams(window.location.search).get('tour') === '1';
    if (forcado) {
      jaIniciado.current = true;
      marcarConcluido();
      void executar('completo');
      return;
    }

    // Auto-start apenas na primeira visita a /empresa/gerar. O cleanup cancela
    // o timer se a rota mudar antes dos 600 ms.
    if (origem !== 'empresa' || pathname !== ROTAS.empresaGerar || !deveAutoIniciar()) {
      return;
    }

    let cancelado = false;
    const timer = window.setTimeout(() => {
      if (cancelado) return;
      jaIniciado.current = true;
      marcarConcluido();
      void executar('empresa');
    }, 600);

    return () => {
      cancelado = true;
      window.clearTimeout(timer);
    };
  }, [executar, origem, pathname]);

  const aoClicar = useCallback(async () => {
    if (iniciando) return;
    setIniciando(true);
    try {
      await executar(origem);
    } finally {
      setIniciando(false);
    }
  }, [executar, iniciando, origem]);

  return (
    <Button
      variant="ghost"
      size="sm"
      onClick={aoClicar}
      disabled={iniciando}
      aria-label={M.tour.verTour}
    >
      {M.tour.verTour}
    </Button>
  );
}
