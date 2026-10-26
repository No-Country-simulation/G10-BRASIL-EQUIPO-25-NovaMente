import { describe, expect, it } from 'vitest';
import { ErroApi, ErroContrato, ErroRede, mensagemDoErro, paraProblema } from './erros';

describe('paraProblema', () => {
  it('usa o corpo quando já é ApiProblema', () => {
    const corpo = { erro: { codigo: 'VALIDACAO', mensagem: 'Inválido', campos: { a: 'b' } } };
    expect(paraProblema(422, corpo)).toEqual(corpo);
  });

  it('cria fallback quando o corpo não segue o contrato', () => {
    const p = paraProblema(502, '<html>Bad gateway</html>');
    expect(p.erro.codigo).toBe('INTERNO');
    expect(p.erro.mensagem).toContain('502');
  });
});

describe('mensagemDoErro', () => {
  it('prefere a mensagem do servidor', () => {
    const e = new ErroApi({ erro: { codigo: 'LIMITE_EXCEDIDO', mensagem: 'Arquivo acima de 10 MB.' } }, 413);
    expect(mensagemDoErro(e)).toBe('Arquivo acima de 10 MB.');
  });

  it('distingue rede, contrato e desconhecido', () => {
    expect(mensagemDoErro(new ErroRede())).toContain('servidor');
    expect(mensagemDoErro(new ErroContrato())).toContain('formato inesperado');
    expect(mensagemDoErro(new Error('x'))).toContain('inesperado');
  });
});
