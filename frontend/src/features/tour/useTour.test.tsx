import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  CHAVE_TOUR,
  VERSAO_TOUR,
  deveAutoIniciar,
  iniciarTour,
  marcarConcluido,
  passosDoTour,
} from './useTour';
import { aguardarElemento, filtrarPassosDisponiveis } from './driver';
import { CHAVE_IDENTIDADE_ALUNO } from '@/features/aluno/useIdentidadeAluno';

const driverMock = vi.hoisted(() => vi.fn());

vi.mock('driver.js', () => ({ driver: driverMock }));

function elementoDoTour(seletor: string) {
  const elemento = document.createElement('div');
  elemento.setAttribute('data-tour', seletor);
  document.body.appendChild(elemento);
}

beforeEach(() => {
  window.localStorage.clear();
  document.body.innerHTML = '';
  driverMock.mockReset();
});

afterEach(() => {
  document.body.innerHTML = '';
});

describe('passosDoTour', () => {
  it('usa o roteiro completo para landing e completo', () => {
    expect(passosDoTour('landing')).toHaveLength(8);
    expect(passosDoTour('completo')).toHaveLength(8);
    expect(passosDoTour('landing')[0].rota).toBe('/');
    expect(passosDoTour('landing')[7].rota).toBe('/aluno');
  });

  it('começa na área da empresa para a origem empresa', () => {
    const passos = passosDoTour('empresa');
    expect(passos).toHaveLength(6);
    expect(passos[0].element).toBe('[data-tour="empresa-nav"]');
    expect(passos[5].element).toBe('[data-tour="aluno-identificacao"]');
  });

  it('reduz a origem aluno ao passo da área do aluno', () => {
    const passos = passosDoTour('aluno');
    expect(passos).toHaveLength(1);
    expect(passos[0].rota).toBe('/aluno');
    expect(passos[0].element).toBe('[data-tour="aluno-identificacao"]');
  });

  it('aponta para o catálogo quando o aluno já está identificado', () => {
    const passos = passosDoTour('aluno', true);
    expect(passos[0].element).toBe('[data-tour="aluno-catalogo"]');
  });
});

describe('filtrarPassosDisponiveis', () => {
  it('pula passo cujo alvo não existe e continua', () => {
    const passos = [
      { element: '[data-tour="a"]', popover: { title: 'A' } },
      { element: '[data-tour="ausente"]', popover: { title: 'Ausente' } },
      { element: '[data-tour="b"]', popover: { title: 'B' } },
    ];

    const disponiveis = filtrarPassosDisponiveis(
      passos,
      (seletor) => seletor !== '[data-tour="ausente"]',
    );

    expect(disponiveis.map((passo) => passo.element)).toEqual([
      '[data-tour="a"]',
      '[data-tour="b"]',
    ]);
  });
});

describe('aguardarElemento', () => {
  it('resolve imediatamente quando o alvo já existe', async () => {
    elementoDoTour('existente');
    await expect(aguardarElemento('[data-tour="existente"]', 20)).resolves.toBe(true);
  });

  it('resolve quando o alvo aparece depois', async () => {
    const espera = aguardarElemento('[data-tour="tardio"]', 1_000);
    setTimeout(() => elementoDoTour('tardio'), 10);
    await expect(espera).resolves.toBe(true);
  });

  it('resolve falso após o limite', async () => {
    await expect(aguardarElemento('[data-tour="nunca"]', 20)).resolves.toBe(false);
  });
});

describe('persistência do tour', () => {
  it('auto-inicia quando não há registro', () => {
    expect(deveAutoIniciar()).toBe(true);
  });

  it('não auto-inicia depois da versão atual', () => {
    window.localStorage.setItem(
      CHAVE_TOUR,
      JSON.stringify({ versao: VERSAO_TOUR, concluido_em: '2026-11-09T10:00:00Z' }),
    );
    expect(deveAutoIniciar()).toBe(false);
  });

  it('auto-inicia quando a versão registrada é antiga ou inválida', () => {
    window.localStorage.setItem(CHAVE_TOUR, JSON.stringify({ versao: 0 }));
    expect(deveAutoIniciar()).toBe(true);
    window.localStorage.setItem(CHAVE_TOUR, '{');
    expect(deveAutoIniciar()).toBe(true);
  });

  it('marca a conclusão com versão e data', () => {
    marcarConcluido();
    const registro = JSON.parse(window.localStorage.getItem(CHAVE_TOUR) ?? '{}');
    expect(registro.versao).toBe(VERSAO_TOUR);
    expect(typeof registro.concluido_em).toBe('string');
  });
});

describe('iniciarTour', () => {
  it('navega até o primeiro passo, cria o driver e avança até o fim', async () => {
    for (const seletor of [
      'empresa-nav',
      'empresa-gerar-form',
      'empresa-historico-lista',
      'empresa-materiais-lista',
      'empresa-alunos-lista',
      'aluno-identificacao',
    ]) {
      elementoDoTour(seletor);
    }

    const fakeDriver = {
      drive: vi.fn(),
      moveTo: vi.fn(),
      destroy: vi.fn(),
    };
    driverMock.mockReturnValue(fakeDriver);
    const navegar = vi.fn();

    await iniciarTour('empresa', navegar);

    expect(driverMock).toHaveBeenCalledTimes(1);
    const config = driverMock.mock.calls[0][0];
    expect(config.steps).toHaveLength(6);
    expect(fakeDriver.drive).toHaveBeenCalledWith(0);
    expect(navegar).toHaveBeenCalledWith('/empresa/gerar');

    config.onNextClick(undefined, config.steps[0], { index: 0, driver: fakeDriver });
    await vi.waitFor(() => expect(fakeDriver.moveTo).toHaveBeenCalledWith(1));

    config.onNextClick(undefined, config.steps[5], { index: 5, driver: fakeDriver });
    await vi.waitFor(() => expect(fakeDriver.destroy).toHaveBeenCalled());

    config.onDestroyed();
    expect(window.localStorage.getItem(CHAVE_TOUR)).toContain('versao');
  });

  it('usa o alvo do catálogo quando o aluno já está identificado', async () => {
    window.localStorage.setItem(
      CHAVE_IDENTIDADE_ALUNO,
      JSON.stringify({ aluno_id: 'A1', nome: 'Ana' }),
    );
    elementoDoTour('aluno-catalogo');
    driverMock.mockReturnValue({ drive: vi.fn(), moveTo: vi.fn(), destroy: vi.fn() });

    await iniciarTour('aluno', vi.fn());

    const config = driverMock.mock.calls[0][0];
    expect(config.steps[0].element).toBe('[data-tour="aluno-catalogo"]');
  });
});
