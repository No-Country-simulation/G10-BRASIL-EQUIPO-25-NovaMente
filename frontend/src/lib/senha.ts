/**
 * Política de senha (igual no backend): 8 a 128 caracteres, com letra
 * maiúscula, letra minúscula, número e símbolo. Espaços não contam como símbolo.
 * Usada só para CRIAR a senha; no login a regra não é conferida no navegador.
 */
export const SENHA_MINIMO = 8;
export const SENHA_MAXIMO = 128;

export interface RequisitoSenha {
  id: 'tamanho' | 'maiuscula' | 'minuscula' | 'numero' | 'simbolo';
  rotulo: string;
  atendido: boolean;
}

export function avaliarSenha(senha: string): RequisitoSenha[] {
  return [
    {
      id: 'tamanho',
      rotulo: `Mínimo de ${SENHA_MINIMO} caracteres`,
      atendido: senha.length >= SENHA_MINIMO && senha.length <= SENHA_MAXIMO,
    },
    { id: 'maiuscula', rotulo: 'Uma letra maiúscula', atendido: /\p{Lu}/u.test(senha) },
    { id: 'minuscula', rotulo: 'Uma letra minúscula', atendido: /\p{Ll}/u.test(senha) },
    { id: 'numero', rotulo: 'Um número', atendido: /\p{N}/u.test(senha) },
    {
      id: 'simbolo',
      rotulo: 'Um símbolo (por exemplo ! @ # $ %)',
      atendido: /[^\p{L}\p{N}\s]/u.test(senha),
    },
  ];
}

export function senhaValida(senha: string): boolean {
  return avaliarSenha(senha).every((requisito) => requisito.atendido);
}
