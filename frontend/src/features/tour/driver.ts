import type { Config, DriveStep, Driver } from 'driver.js';
import { M } from '@/lib/mensagens';
import './tour.css';

/** Passo do tour com a rota em que o alvo deve estar montado. */
export type PassoTour = DriveStep & {
  element: string;
  rota: string;
};

export interface OpcoesTour {
  aoEncerrar?: () => void;
  aoAvancar?: (indice: number, driver: Driver) => void | Promise<void>;
  aoVoltar?: (indice: number, driver: Driver) => void | Promise<void>;
}

/**
 * Remove passos cujo alvo não está no DOM. Usado depois de navegar quando o
 * passo continua ausente (por exemplo, rota alterada ou estado inesperado).
 */
export function filtrarPassosDisponiveis<T extends { element?: string | Element }>(
  passos: T[],
  existe: (seletor: string) => boolean = (seletor) => Boolean(document.querySelector(seletor)),
): T[] {
  return passos.filter((passo) => {
    if (typeof passo.element === 'string') return existe(passo.element);
    return Boolean(passo.element);
  });
}

/**
 * Aguarda o alvo aparecer por até `tempoLimite` ms. O MutationObserver cobre a
 * troca de rota do Next, que monta a nova tela depois do `router.push`.
 */
export function aguardarElemento(seletor: string, tempoLimite = 2500): Promise<boolean> {
  if (typeof document === 'undefined') return Promise.resolve(false);
  if (document.querySelector(seletor)) return Promise.resolve(true);

  return new Promise<boolean>((resolver) => {
    let finalizado = false;

    const finalizar = (encontrado: boolean) => {
      if (finalizado) return;
      finalizado = true;
      observer.disconnect();
      clearTimeout(timer);
      resolver(encontrado);
    };

    const observer = new MutationObserver(() => {
      if (document.querySelector(seletor)) finalizar(true);
    });

    const timer = setTimeout(() => finalizar(false), tempoLimite);
    observer.observe(document.documentElement, {
      childList: true,
      subtree: true,
      attributes: true,
    });
  });
}

function prefereMovimentoReduzido(): boolean {
  return (
    typeof window !== 'undefined' &&
    typeof window.matchMedia === 'function' &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches
  );
}

/**
 * Cria o driver já configurado com os textos e a acessibilidade do produto.
 * O import de `driver.js` é dinâmico para manter a lib fora do bundle inicial.
 */
export async function criarDriver(
  passos: PassoTour[],
  opcoes: OpcoesTour = {},
): Promise<Driver> {
  const { driver } = await import('driver.js');
  const reduzirMovimento = prefereMovimentoReduzido();

  const config: Config = {
    steps: passos.map((passo) => ({
      element: passo.element,
      popover: passo.popover,
    })) as DriveStep[],
    showProgress: true,
    progressText: M.tour.progresso,
    nextBtnText: M.tour.proximo,
    prevBtnText: M.tour.anterior,
    doneBtnText: M.tour.concluir,
    closeBtnLabel: M.tour.pular,
    overlayOpacity: 0.6,
    stagePadding: 8,
    stageRadius: 8,
    popoverClass: 'novamente-tour',
    animate: !reduzirMovimento,
    smoothScroll: !reduzirMovimento,
    allowClose: true,
    allowKeyboardControl: true,
    onNextClick: (_elemento, _passo, contexto) => {
      void opcoes.aoAvancar?.(contexto.index ?? 0, contexto.driver);
    },
    onPrevClick: (_elemento, _passo, contexto) => {
      void opcoes.aoVoltar?.(contexto.index ?? 0, contexto.driver);
    },
    onDestroyed: () => opcoes.aoEncerrar?.(),
  };

  return driver(config);
}
