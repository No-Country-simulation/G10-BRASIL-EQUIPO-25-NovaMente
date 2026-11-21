import { describe, expect, it } from 'vitest';
import { destinoPadrao, destinoSeguro } from './useSessao';

describe('destinoSeguro', () => {
  it('usa o destino padrão do perfil quando não há `proximo`', () => {
    expect(destinoSeguro(null, 'empresa')).toBe('/empresa/gerar');
    expect(destinoSeguro(undefined, 'aluno')).toBe('/aluno');
    expect(destinoPadrao('empresa')).toBe('/empresa/gerar');
  });

  it('aceita caminhos internos do próprio perfil', () => {
    expect(destinoSeguro('/empresa/materiais', 'empresa')).toBe('/empresa/materiais');
    expect(destinoSeguro('/empresa/resultado/abc', 'empresa')).toBe('/empresa/resultado/abc');
    expect(destinoSeguro('/aluno/materiais/xyz', 'aluno')).toBe('/aluno/materiais/xyz');
    expect(destinoSeguro('/aluno', 'aluno')).toBe('/aluno');
  });

  it('recusa destino de outro perfil', () => {
    expect(destinoSeguro('/empresa/gerar', 'aluno')).toBe('/aluno');
    expect(destinoSeguro('/aluno/materiais/x', 'empresa')).toBe('/empresa/gerar');
  });

  it('recusa endereços externos e formatos suspeitos (redirecionamento aberto)', () => {
    expect(destinoSeguro('https://malicioso.com/empresa', 'empresa')).toBe('/empresa/gerar');
    expect(destinoSeguro('//malicioso.com', 'empresa')).toBe('/empresa/gerar');
    expect(destinoSeguro('/\\malicioso.com', 'empresa')).toBe('/empresa/gerar');
    expect(destinoSeguro('/empresaX', 'empresa')).toBe('/empresa/gerar');
    expect(destinoSeguro('javascript:alert(1)', 'aluno')).toBe('/aluno');
  });
});
