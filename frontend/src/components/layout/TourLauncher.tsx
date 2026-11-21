'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { usePathname } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { useConsentimento } from '@/features/privacidade/consentimento';
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
  /** Injeta o início nos testes e no auto-start. `false` = nenhum alvo iniciou. */
  iniciar?: (origem: OrigemTour) => Promise<unknown>;
  /** Conta logada: a conclusão do tour é guardada por conta. */
  conta?: string;
  /** Falso enquanto não há sessão confirmada (login ligado): não abre sozinho. */
  autoIniciar?: boolean;
}

export function TourLauncher({ origem, iniciar, conta, autoIniciar = true }: TourLauncherProps) {
  const pathname = usePathname();
  const { iniciarTour } = useTour(conta);
  const executar = iniciar ?? iniciarTour;
  const [iniciando, setIniciando] = useState(false);
  const jaIniciado = useRef(false);
  // O tour sozinho espera o usuário decidir sobre os cookies: dois avisos ao mesmo tempo atrapalham.
  const { decidido } = useConsentimento();

  // Só grava a conclusão depois que o tour realmente iniciou. Uma falha no
  // import dinâmico (ou nenhum alvo disponível) não desabilita o tour para
  // sempre; o `onDestroyed` do driver também grava ao concluir/pular.
  const iniciarComSeguranca = useCallback(
    async (pontoDeEntrada: OrigemTour) => {
      try {
        const iniciado = await executar(pontoDeEntrada);
        if (iniciado !== false) marcarConcluido(conta);
      } catch (falha) {
        console.error('[tour] Falha ao iniciar o tour.', falha);
      }
    },
    [executar, conta],
  );

  useEffect(() => {
    if (jaIniciado.current) return;

    const forcado =
      typeof window !== 'undefined' &&
      new URLSearchParams(window.location.search).get('tour') === '1';
    if (forcado) {
      jaIniciado.current = true;
      void iniciarComSeguranca('completo');
      return;
    }

    // Auto-start apenas na primeira visita a /empresa/gerar. O cleanup cancela
    // o timer se a rota mudar antes dos 600 ms.
    if (
      !autoIniciar ||
      !decidido ||
      origem !== 'empresa' ||
      pathname !== ROTAS.empresaGerar ||
      !deveAutoIniciar(conta)
    ) {
      return;
    }

    let cancelado = false;
    const timer = window.setTimeout(() => {
      if (cancelado) return;
      jaIniciado.current = true;
      void iniciarComSeguranca('empresa');
    }, 600);

    return () => {
      cancelado = true;
      window.clearTimeout(timer);
    };
  }, [iniciarComSeguranca, origem, pathname, autoIniciar, decidido, conta]);

  const aoClicar = useCallback(async () => {
    if (iniciando) return;
    setIniciando(true);
    try {
      await iniciarComSeguranca(origem);
    } finally {
      setIniciando(false);
    }
  }, [iniciarComSeguranca, iniciando, origem]);

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
