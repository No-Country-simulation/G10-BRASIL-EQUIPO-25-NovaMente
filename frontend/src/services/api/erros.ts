import type { ApiProblema } from '@/types/novamente';
import { ApiProblemaSchema } from '@/types/schemas';
import { M } from '@/lib/mensagens';

export class ErroApi extends Error {
  constructor(
    public readonly problema: ApiProblema,
    public readonly status: number,
  ) {
    super(problema.erro.mensagem);
    this.name = 'ErroApi';
  }
}

export class ErroRede extends Error {
  constructor() {
    super(M.erro.rede);
    this.name = 'ErroRede';
  }
}

export class ErroContrato extends Error {
  constructor(public readonly detalhe: string = '') {
    super(M.erro.contrato);
    this.name = 'ErroContrato';
  }
}

export function paraProblema(status: number, corpo: unknown): ApiProblema {
  const analisado = ApiProblemaSchema.safeParse(corpo);
  if (analisado.success) return analisado.data;
  return {
    erro: {
      codigo: 'INTERNO',
      mensagem: `Erro inesperado no servidor (HTTP ${status}).`,
    },
  };
}

export function mensagemDoErro(erro: unknown): string {
  if (erro instanceof ErroApi) return erro.problema.erro.mensagem;
  if (erro instanceof ErroRede) return erro.message;
  if (erro instanceof ErroContrato) return erro.message;
  return M.erro.generico;
}
