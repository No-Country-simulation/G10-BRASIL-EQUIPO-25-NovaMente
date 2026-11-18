import { act, render, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi, type Mock } from 'vitest';
import { SkinProvider } from '@/features/theme/SkinProvider';
import { useSkin } from '@/features/theme/useSkin';
import { NeuralBackground } from './NeuralBackground';

type Contexto = Record<string, Mock> & { chamadas: (nome: string) => number };

/** Contexto 2D falso: qualquer método vira um vi.fn, e propriedades são aceitas. */
function contextoFalso(): Contexto {
  const metodos: Record<string, Mock> = {};
  const alvo = {
    chamadas: (nome: string) => metodos[nome]?.mock.calls.length ?? 0,
  } as Record<string, unknown>;
  return new Proxy(alvo, {
    get(objeto, chave: string) {
      if (chave in objeto) return objeto[chave];
      metodos[chave] ??= vi.fn();
      return metodos[chave];
    },
    set(objeto, chave: string, valor) {
      objeto[chave] = valor;
      return true;
    },
  }) as unknown as Contexto;
}

let ctx: Contexto;
let raf: Mock;
let cancelar: Mock;
let ouvintesMovimento: Array<(evento: { matches: boolean }) => void>;

function simularMovimentoReduzido(reduzido: boolean) {
  ouvintesMovimento = [];
  window.matchMedia = vi.fn().mockImplementation((consulta: string) => ({
    matches: consulta.includes('prefers-reduced-motion') && reduzido,
    media: consulta,
    addEventListener: vi.fn((_tipo: string, ouvinte: (evento: { matches: boolean }) => void) => {
      ouvintesMovimento.push(ouvinte);
    }),
    removeEventListener: vi.fn(),
  })) as unknown as typeof window.matchMedia;
}

function proximoQuadro(): (agora: number) => void {
  return raf.mock.calls[raf.mock.calls.length - 1][0];
}

beforeEach(() => {
  ctx = contextoFalso();
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(
    ctx as unknown as CanvasRenderingContext2D,
  );
  let id = 0;
  raf = vi.fn(() => ++id);
  cancelar = vi.fn();
  // spyOn, e não stubGlobal: unstubAllGlobals apagaria o ResizeObserver do setup.
  vi.spyOn(window, 'requestAnimationFrame').mockImplementation(raf);
  vi.spyOn(window, 'cancelAnimationFrame').mockImplementation(cancelar);
  simularMovimentoReduzido(false);
});

afterEach(() => {
  vi.restoreAllMocks();
  Object.defineProperty(document, 'hidden', { configurable: true, get: () => false });
});

describe('NeuralBackground', () => {
  it('desenha num canvas decorativo, fixo e sem eventos de ponteiro', () => {
    const { container } = render(<NeuralBackground />);
    const canvas = container.querySelector('canvas')!;
    expect(canvas).toHaveAttribute('aria-hidden', 'true');
    expect(canvas.style.position).toBe('fixed');
    expect(canvas.style.pointerEvents).toBe('none');
    expect(raf).toHaveBeenCalledTimes(1);
  });

  it('não lança nem agenda nada quando getContext devolve null', () => {
    vi.mocked(HTMLCanvasElement.prototype.getContext).mockReturnValue(null);
    expect(() => render(<NeuralBackground />).unmount()).not.toThrow();
    expect(raf).not.toHaveBeenCalled();
  });

  it('cancela o quadro agendado e solta os ouvintes ao desmontar', () => {
    const remover = vi.spyOn(document, 'removeEventListener');
    const { unmount } = render(<NeuralBackground />);
    const agendado = raf.mock.results[0].value;
    unmount();
    expect(cancelar).toHaveBeenCalledWith(agendado);
    expect(remover).toHaveBeenCalledWith('visibilitychange', expect.any(Function));
  });

  it('com movimento reduzido desenha um quadro e não inicia o loop', () => {
    simularMovimentoReduzido(true);
    render(<NeuralBackground />);
    expect(raf).not.toHaveBeenCalled();
    expect(ctx.chamadas('clearRect')).toBe(1);
    expect(ctx.chamadas('fill')).toBeGreaterThan(0);
  });

  it('reage à mudança da preferência de movimento em tempo real', () => {
    render(<NeuralBackground />);
    act(() => ouvintesMovimento.forEach((ouvinte) => ouvinte({ matches: true })));
    expect(cancelar).toHaveBeenCalled();
    const desenhos = ctx.chamadas('clearRect');
    expect(desenhos).toBe(1); // o quadro estático
    act(() => ouvintesMovimento.forEach((ouvinte) => ouvinte({ matches: false })));
    expect(raf).toHaveBeenCalledTimes(2);
  });

  it('pausa com a aba escondida e retoma ao voltar', () => {
    render(<NeuralBackground />);
    Object.defineProperty(document, 'hidden', { configurable: true, get: () => true });
    act(() => {
      document.dispatchEvent(new Event('visibilitychange'));
    });
    expect(cancelar).toHaveBeenCalledTimes(1);
    Object.defineProperty(document, 'hidden', { configurable: true, get: () => false });
    act(() => {
      document.dispatchEvent(new Event('visibilitychange'));
    });
    expect(raf).toHaveBeenCalledTimes(2);
  });

  it('com a rede densa demais para o buffer, nenhum pulso usa índice inválido', () => {
    // Tela de 100 × 100: o mínimo de 30 nós fica a menos de 90 px uns dos outros,
    // com mais pares vizinhos (até 435) do que cabem no buffer (30 × 8 = 240).
    // Um par lido fora do buffer vira (0, 0) no Int32Array: o pulso fica parado
    // no nó 0, com a cabeça (raio 1,8) e a cauda (raio 1,3) no mesmo ponto.
    const tamanho = { configurable: true, value: 100 };
    const largura = Object.getOwnPropertyDescriptor(window, 'innerWidth');
    const altura = Object.getOwnPropertyDescriptor(window, 'innerHeight');
    Object.defineProperty(window, 'innerWidth', tamanho);
    Object.defineProperty(window, 'innerHeight', tamanho);
    try {
      render(<NeuralBackground />);
      const arcos = () => (ctx.arc as Mock).mock.calls as number[][];
      let cabecas = 0;
      for (let k = 0; k < 300; k++) {
        // ~10 s, vários pulsos
        const antes = arcos().length;
        expect(() => proximoQuadro()(k * 34)).not.toThrow();
        const doQuadro = arcos().slice(antes);
        const caudas = new Set(doQuadro.filter((a) => a[2] === 1.3).map((a) => `${a[0]},${a[1]}`));
        for (const [x, y, raio] of doQuadro) {
          if (raio !== 1.8) continue;
          cabecas++;
          expect(caudas.has(`${x},${y}`)).toBe(false);
        }
      }
      expect(cabecas).toBeGreaterThan(0);
      for (const nome of ['arc', 'moveTo', 'lineTo']) {
        for (const argumentos of (ctx[nome] as Mock).mock.calls) {
          expect(argumentos.every((valor: unknown) => Number.isFinite(valor))).toBe(true);
        }
      }
    } finally {
      if (largura) Object.defineProperty(window, 'innerWidth', largura);
      if (altura) Object.defineProperty(window, 'innerHeight', altura);
    }
  });

  it('limita a ~30 quadros por segundo e anima arestas, nós e pulsos', () => {
    render(<NeuralBackground />);
    proximoQuadro()(0); // primeiro quadro: só desenha
    expect(ctx.chamadas('clearRect')).toBe(1);
    proximoQuadro()(10); // 10 ms depois: cedo demais
    expect(ctx.chamadas('clearRect')).toBe(1);
    proximoQuadro()(34);
    expect(ctx.chamadas('clearRect')).toBe(2);
    for (let k = 2; k < 300; k++) proximoQuadro()(k * 34); // ~10 s
    expect(ctx.chamadas('clearRect')).toBe(300);
    expect(ctx.chamadas('stroke')).toBeGreaterThan(0);
    expect(ctx.chamadas('arc')).toBeGreaterThan(0);
  });
});

describe('SkinProvider com a skin Neural', () => {
  beforeEach(() => {
    localStorage.clear();
    useSkin.setState({ skin: 'violeta', modo: 'dark' });
  });

  it('não monta o canvas em outra skin e monta/desmonta ao trocar', async () => {
    const { container } = render(
      <SkinProvider>
        <p>conteúdo</p>
      </SkinProvider>,
    );
    expect(container.querySelector('canvas')).toBeNull();

    act(() => useSkin.setState({ skin: 'neural' }));
    await waitFor(() => expect(container.querySelector('canvas')).not.toBeNull());
    expect(document.documentElement.dataset.skin).toBe('neural');

    act(() => useSkin.setState({ skin: 'ciano' }));
    expect(container.querySelector('canvas')).toBeNull();
    expect(cancelar).toHaveBeenCalled();
  });
});
