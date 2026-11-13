'use client';

import { useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { CHAVE_IDENTIDADE_ALUNO } from '@/features/aluno/useIdentidadeAluno';
import { ROTAS } from '@/lib/rotas';
import { M } from '@/lib/mensagens';
import type { PassoTour } from './driver';

export const CHAVE_TOUR = 'novamente.tour';
export const VERSAO_TOUR = 1;

export type OrigemTour = 'landing' | 'empresa' | 'aluno' | 'completo';

const PASSOS: PassoTour[] = [
  {
    element: '[data-tour="landing-hero"]',
    rota: ROTAS.landing,
    popover: {
      title: M.tour.passos.boasVindas.titulo,
      description: M.tour.passos.boasVindas.descricao,
    },
  },
  {
    element: '[data-tour="landing-publicos"]',
    rota: ROTAS.landing,
    popover: {
      title: M.tour.passos.publicos.titulo,
      description: M.tour.passos.publicos.descricao,
    },
  },
  {
    element: '[data-tour="empresa-nav"]',
    rota: ROTAS.empresaGerar,
    popover: {
      title: M.tour.passos.empresa.titulo,
      description: M.tour.passos.empresa.descricao,
    },
  },
  {
    element: '[data-tour="empresa-gerar-form"]',
    rota: ROTAS.empresaGerar,
    popover: {
      title: M.tour.passos.gerar.titulo,
      description: M.tour.passos.gerar.descricao,
    },
  },
  {
    element: '[data-tour="empresa-historico-lista"]',
    rota: ROTAS.empresaHistorico,
    popover: {
      title: M.tour.passos.historico.titulo,
      description: M.tour.passos.historico.descricao,
    },
  },
  {
    element: '[data-tour="empresa-materiais-lista"]',
    rota: ROTAS.empresaMateriais,
    popover: {
      title: M.tour.passos.materiais.titulo,
      description: M.tour.passos.materiais.descricao,
    },
  },
  {
    element: '[data-tour="empresa-alunos-lista"]',
    rota: ROTAS.empresaAlunos,
    popover: {
      title: M.tour.passos.alunos.titulo,
      description: M.tour.passos.alunos.descricao,
    },
  },
  {
    element: '[data-tour="aluno-identificacao"]',
    rota: ROTAS.aluno,
    popover: {
      title: M.tour.passos.aluno.titulo,
      description: M.tour.passos.aluno.descricao,
    },
  },
];

function alunoIdentificadoNoNavegador(): boolean {
  if (typeof window === 'undefined') return false;
  try {
    const bruto = window.localStorage.getItem(CHAVE_IDENTIDADE_ALUNO);
    if (!bruto) return false;
    const dados = JSON.parse(bruto) as { aluno_id?: unknown };
    return typeof dados.aluno_id === 'string' && dados.aluno_id.length > 0;
  } catch {
    return false;
  }
}

/** Subconjunto de passos por ponto de entrada. */
export function passosDoTour(
  origem: OrigemTour,
  alunoIdentificado = false,
): PassoTour[] {
  const passos = PASSOS.map((passo) =>
    passo.rota === ROTAS.aluno
      ? {
          ...passo,
          element: alunoIdentificado
            ? '[data-tour="aluno-catalogo"]'
            : '[data-tour="aluno-identificacao"]',
        }
      : passo,
  );

  switch (origem) {
    case 'empresa':
      return passos.slice(2);
    case 'aluno':
      return passos.slice(7);
    case 'landing':
    case 'completo':
    default:
      return passos;
  }
}

/** Auto-start só após a primeira visita e respeitando a versão do roteiro. */
export function deveAutoIniciar(): boolean {
  if (typeof window === 'undefined') return false;
  const bruto = window.localStorage.getItem(CHAVE_TOUR);
  if (!bruto) return true;
  try {
    const dados = JSON.parse(bruto) as { versao?: unknown };
    return typeof dados.versao !== 'number' || dados.versao < VERSAO_TOUR;
  } catch {
    return true;
  }
}

export function marcarConcluido(): void {
  if (typeof window === 'undefined') return;
  window.localStorage.setItem(
    CHAVE_TOUR,
    JSON.stringify({ versao: VERSAO_TOUR, concluido_em: new Date().toISOString() }),
  );
}

async function localizarPasso(
  passos: PassoTour[],
  inicio: number,
  direcao: 1 | -1,
  navegar: (rota: string) => void,
): Promise<number | null> {
  const { aguardarElemento } = await import('./driver');

  for (let indice = inicio; indice >= 0 && indice < passos.length; indice += direcao) {
    const passo = passos[indice];
    if (window.location.pathname !== passo.rota) navegar(passo.rota);
    if (await aguardarElemento(passo.element, 2500)) return indice;
  }
  return null;
}

/**
 * Executa o tour navegando entre as telas reais. Cada passo aguarda seu alvo
 * por até 2.500 ms; se ele não existir, o passo é pulado e o tour continua.
 */
export async function iniciarTour(
  origem: OrigemTour,
  navegar: (rota: string) => void,
): Promise<boolean> {
  if (typeof window === 'undefined') return false;

  const passos = passosDoTour(origem, alunoIdentificadoNoNavegador());
  const primeiro = await localizarPasso(passos, 0, 1, navegar);
  if (primeiro === null) return false;

  const { criarDriver } = await import('./driver');
  const driver = await criarDriver(passos, {
    aoEncerrar: marcarConcluido,
    aoAvancar: async (indice, instancia) => {
      const proximo = await localizarPasso(passos, indice + 1, 1, navegar);
      if (proximo === null) instancia.destroy();
      else instancia.moveTo(proximo);
    },
    aoVoltar: async (indice, instancia) => {
      const anterior = await localizarPasso(passos, indice - 1, -1, navegar);
      if (anterior !== null) instancia.moveTo(anterior);
    },
  });

  driver.drive(primeiro);
  return true;
}

/** Versão do tour que usa o router do Next para navegar entre as telas. */
export function useTour() {
  const router = useRouter();

  const iniciar = useCallback(
    (origem: OrigemTour) => iniciarTour(origem, (rota) => router.push(rota)),
    [router],
  );

  return { iniciarTour: iniciar };
}
