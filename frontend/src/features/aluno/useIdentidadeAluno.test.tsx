import { act, renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it } from 'vitest';
import { CHAVE_IDENTIDADE_ALUNO, useIdentidadeAluno } from './useIdentidadeAluno';

beforeEach(() => {
  window.localStorage.clear();
});

describe('useIdentidadeAluno', () => {
  it('lê uma identidade válida já persistida', () => {
    window.localStorage.setItem(
      CHAVE_IDENTIDADE_ALUNO,
      JSON.stringify({ aluno_id: 'A1', nome: 'Ana Beatriz' }),
    );

    const { result } = renderHook(() => useIdentidadeAluno());

    expect(result.current.aluno).toEqual({ aluno_id: 'A1', nome: 'Ana Beatriz' });
  });

  it('ignora JSON corrompido ou fora do contrato', () => {
    window.localStorage.setItem(CHAVE_IDENTIDADE_ALUNO, '{');
    const corrompido = renderHook(() => useIdentidadeAluno());
    expect(corrompido.result.current.aluno).toBeNull();
    corrompido.unmount();

    window.localStorage.setItem(
      CHAVE_IDENTIDADE_ALUNO,
      JSON.stringify({ aluno_id: 'A1' }),
    );
    const incompleto = renderHook(() => useIdentidadeAluno());
    expect(incompleto.result.current.aluno).toBeNull();
  });

  it('identifica, persiste e limpa a identidade', () => {
    const { result } = renderHook(() => useIdentidadeAluno());
    expect(result.current.aluno).toBeNull();

    act(() => result.current.identificar({ aluno_id: 'A1', nome: 'Ana Beatriz' }));

    expect(result.current.aluno).toEqual({ aluno_id: 'A1', nome: 'Ana Beatriz' });
    expect(window.localStorage.getItem(CHAVE_IDENTIDADE_ALUNO)).toContain('A1');

    act(() => result.current.trocarAluno());

    expect(result.current.aluno).toBeNull();
    expect(window.localStorage.getItem(CHAVE_IDENTIDADE_ALUNO)).toBeNull();
  });

  it('expõe limpar como alias de trocarAluno', () => {
    window.localStorage.setItem(
      CHAVE_IDENTIDADE_ALUNO,
      JSON.stringify({ aluno_id: 'A1', nome: 'Ana Beatriz' }),
    );
    const { result } = renderHook(() => useIdentidadeAluno());

    act(() => result.current.limpar());

    expect(result.current.aluno).toBeNull();
    expect(window.localStorage.getItem(CHAVE_IDENTIDADE_ALUNO)).toBeNull();
  });
});
