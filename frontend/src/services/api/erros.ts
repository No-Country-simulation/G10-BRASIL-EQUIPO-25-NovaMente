import type { ApiProblema } from '@/types/novamente';
import { ApiProblemaSchema } from '@/types/schemas';
import { M } from '@/lib/mensagens';

export class ErroApi extends Error {
  constructor(
    public readonly problema: ApiProblema,
    public readonly status: number,
    // Segundos do cabeçalho Retry-After (429/503), quando o servidor informa.
    public readonly retryAfter?: number,
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

/** Lê o Retry-After em segundos; ignora data HTTP e valores inválidos. */
export function lerRetryAfter(resposta: Response): number | undefined {
  const bruto = resposta.headers?.get('Retry-After') ?? null;
  if (bruto === null || !/^\d+$/.test(bruto.trim())) return undefined;
  const segundos = Number(bruto);
  return segundos > 0 ? segundos : undefined;
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

/** Como `mensagemDoErro`, com a espera do Retry-After quando o servidor a informa (429/503). */
export function mensagemComEspera(erro: unknown): string {
  const base = mensagemDoErro(erro);
  if (erro instanceof ErroApi && erro.retryAfter) {
    return `${base} ${M.erro.tenteEm(erro.retryAfter)}`;
  }
  return base;
}
