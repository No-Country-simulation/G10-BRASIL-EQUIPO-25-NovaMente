import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { TourLauncher } from './TourLauncher';
import { CHAVE_TOUR } from '@/features/tour/useTour';

const mocks = vi.hoisted(() => ({
  push: vi.fn(),
  replace: vi.fn(),
  pathname: '/',
}));

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: mocks.push, replace: mocks.replace }),
  usePathname: () => mocks.pathname,
  useSearchParams: () => new URLSearchParams(),
}));

beforeEach(() => {
  window.localStorage.clear();
  window.history.replaceState({}, '', '/');
  mocks.push.mockReset();
  mocks.replace.mockReset();
  mocks.pathname = '/';
});

afterEach(() => {
  vi.useRealTimers();
});

describe('TourLauncher', () => {
  it('auto-inicia uma única vez em /empresa/gerar', async () => {
    mocks.pathname = '/empresa/gerar';
    const iniciar = vi.fn().mockResolvedValue(undefined);

    render(<TourLauncher origem="empresa" iniciar={iniciar} />);

    await waitFor(() => expect(iniciar).toHaveBeenCalledWith('empresa'), {
      timeout: 1_500,
    });
    expect(iniciar).toHaveBeenCalledTimes(1);
    expect(window.localStorage.getItem(CHAVE_TOUR)).toContain('versao');
  });

  it('não auto-inicia em /aluno', () => {
    vi.useFakeTimers();
    mocks.pathname = '/aluno';
    const iniciar = vi.fn().mockResolvedValue(undefined);

    render(<TourLauncher origem="aluno" iniciar={iniciar} />);
    act(() => vi.advanceTimersByTime(700));

    expect(iniciar).not.toHaveBeenCalled();
  });

  it('não auto-inicia em deep link da empresa que não seja /empresa/gerar', () => {
    vi.useFakeTimers();
    mocks.pathname = '/empresa/materiais';
    const iniciar = vi.fn().mockResolvedValue(undefined);

    render(<TourLauncher origem="empresa" iniciar={iniciar} />);
    act(() => vi.advanceTimersByTime(700));

    expect(iniciar).not.toHaveBeenCalled();
  });

  it('não auto-inicia quando o tour já foi concluído', () => {
    vi.useFakeTimers();
    mocks.pathname = '/empresa/gerar';
    window.localStorage.setItem(
      CHAVE_TOUR,
      JSON.stringify({ versao: 1, concluido_em: '2026-11-09T10:00:00Z' }),
    );
    const iniciar = vi.fn().mockResolvedValue(undefined);

    render(<TourLauncher origem="empresa" iniciar={iniciar} />);
    act(() => vi.advanceTimersByTime(700));

    expect(iniciar).not.toHaveBeenCalled();
  });

  it('reinicia pelo botão mesmo depois de concluído', async () => {
    window.localStorage.setItem(
      CHAVE_TOUR,
      JSON.stringify({ versao: 1, concluido_em: '2026-11-09T10:00:00Z' }),
    );
    const iniciar = vi.fn().mockResolvedValue(undefined);

    render(<TourLauncher origem="landing" iniciar={iniciar} />);
    await userEvent.click(screen.getByRole('button', { name: /ver tour/i }));

    expect(iniciar).toHaveBeenCalledWith('landing');
  });

  it('inicia o roteiro completo quando ?tour=1 está na URL', async () => {
    window.history.replaceState({}, '', '/aluno?tour=1');
    mocks.pathname = '/aluno';
    const iniciar = vi.fn().mockResolvedValue(undefined);

    render(<TourLauncher origem="aluno" iniciar={iniciar} />);

    await waitFor(() => expect(iniciar).toHaveBeenCalledWith('completo'));
    expect(window.localStorage.getItem(CHAVE_TOUR)).toContain('versao');
  });

  it('não grava conclusão quando nenhum alvo do tour inicia', async () => {
    window.history.replaceState({}, '', '/aluno?tour=1');
    mocks.pathname = '/aluno';
    const iniciar = vi.fn().mockResolvedValue(false);

    render(<TourLauncher origem="aluno" iniciar={iniciar} />);

    await waitFor(() => expect(iniciar).toHaveBeenCalledWith('completo'));
    expect(window.localStorage.getItem(CHAVE_TOUR)).toBeNull();
  });

  it('registra a falha sem desabilitar o tour para sempre', async () => {
    mocks.pathname = '/empresa/gerar';
    const iniciar = vi.fn().mockRejectedValue(new Error('falha no import dinâmico'));
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {});

    render(<TourLauncher origem="empresa" iniciar={iniciar} />);

    await waitFor(() => expect(iniciar).toHaveBeenCalledWith('empresa'));
    await waitFor(() => expect(consoleError).toHaveBeenCalled());
    expect(window.localStorage.getItem(CHAVE_TOUR)).toBeNull();

    consoleError.mockRestore();
  });
});
