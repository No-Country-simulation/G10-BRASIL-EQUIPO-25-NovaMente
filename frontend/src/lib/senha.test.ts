import { describe, expect, it } from 'vitest';
import { avaliarSenha, senhaValida, SENHA_MAXIMO } from './senha';

const atendidos = (senha: string) =>
  avaliarSenha(senha)
    .filter((requisito) => requisito.atendido)
    .map((requisito) => requisito.id);

describe('política de senha', () => {
  it('aceita senha com 8+ caracteres, maiúscula, minúscula, número e símbolo', () => {
    expect(senhaValida('Aluno@1234')).toBe(true);
    expect(senhaValida('Ab1!cdef')).toBe(true);
    expect(senhaValida('Ação#2026x')).toBe(true);
  });

  it('recusa quando falta cada um dos requisitos', () => {
    expect(senhaValida('Ab1!cde')).toBe(false); // 7 caracteres
    expect(senhaValida('abcdef1!')).toBe(false); // sem maiúscula
    expect(senhaValida('ABCDEF1!')).toBe(false); // sem minúscula
    expect(senhaValida('Abcdefg!')).toBe(false); // sem número
    expect(senhaValida('Abcdefg1')).toBe(false); // sem símbolo
  });

  it('espaço não conta como símbolo', () => {
    expect(senhaValida('Abcdef 1')).toBe(false);
  });

  it('marca cada requisito conforme é atendido', () => {
    expect(atendidos('')).toEqual([]);
    expect(atendidos('abc')).toEqual(['minuscula']);
    expect(atendidos('Abc1')).toEqual(['maiuscula', 'minuscula', 'numero']);
    expect(atendidos('Abc1!xyz')).toHaveLength(5);
  });

  it('recusa senha acima do tamanho máximo', () => {
    expect(senhaValida(`Aa1!${'x'.repeat(SENHA_MAXIMO)}`)).toBe(false);
  });
});
