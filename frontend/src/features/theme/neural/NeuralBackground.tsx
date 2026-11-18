'use client';

import { useEffect, useRef } from 'react';
import {
  avancarPulsos,
  construirGrade,
  criarGrade,
  criarPrng,
  criarPulsos,
  distanciaVizinho,
  gerarRede,
  iniciarPulso,
  passo,
  percorrerPares,
  type Rede,
} from './geometria';

/** Teto de ~30 quadros por segundo (com 1 ms de folga para o relógio do rAF). */
const QUADRO_MINIMO_MS = 1000 / 30 - 1;
/** Acima disto (aba voltando, travada longa) o passo é cortado, sem salto. */
const DT_MAXIMO = 0.1;
const DPR_MAXIMO = 1.5;
const ESPERA_REDIMENSIONAR_MS = 150;
const SEMENTE = 20_261_118;
/** Faixas de opacidade das arestas: um stroke por faixa, em vez de um por aresta. */
const FAIXAS = 4;
/** Arestas guardadas por nó no buffer do quadro; o excedente simplesmente não é desenhado. */
const ARESTAS_POR_NO = 8;
const DURACAO_PULSO_S = 1.4;
const INTERVALO_PULSO_MIN_S = 0.6;
const INTERVALO_PULSO_MAX_S = 1.8;
/** Posições da cauda do pulso, em fração da aresta atrás da cabeça. */
const CAUDA = [0, 0.06, 0.12] as const;
const CONSULTA_MOVIMENTO_REDUZIDO = '(prefers-reduced-motion: reduce)';

const ESTILO_CANVAS: React.CSSProperties = {
  position: 'fixed',
  inset: 0,
  width: '100%',
  height: '100%',
  zIndex: -1,
  pointerEvents: 'none',
  display: 'block',
};

type Rgb = readonly [number, number, number];

interface Paleta {
  arestas: string[];
  ponto: string;
  triangulo: string;
  pulso: string[];
}

function lerCor(valor: string, padrao: Rgb): Rgb {
  const hex = valor.trim().replace('#', '');
  const cheio = hex.length === 3 ? hex.replace(/./g, (c) => c + c) : hex;
  if (!/^[0-9a-f]{6}$/i.test(cheio)) return padrao;
  return [0, 2, 4].map((i) => parseInt(cheio.slice(i, i + 2), 16)) as unknown as Rgb;
}

function misturar(a: Rgb, b: Rgb, peso: number): Rgb {
  return [0, 1, 2].map((i) => Math.round(a[i] * (1 - peso) + b[i] * peso)) as unknown as Rgb;
}

const rgba = ([r, g, b]: Rgb, alfa: number) => `rgba(${r}, ${g}, ${b}, ${alfa.toFixed(3)})`;

/** Cores lidas dos tokens da skin; no modo claro tudo fica mais transparente. */
function montarPaleta(raiz: HTMLElement): Paleta {
  const estilo = getComputedStyle(raiz);
  const acento = lerCor(estilo.getPropertyValue('--accent'), [118, 185, 0]);
  const texto = lerCor(estilo.getPropertyValue('--fg'), [238, 242, 234]);
  const fator = raiz.dataset.modo === 'light' ? 0.6 : 1;
  const verdeClaro = misturar(acento, texto, 0.55);
  return {
    arestas: Array.from({ length: FAIXAS }, (_, f) =>
      rgba(acento, (0.04 + (0.14 * (f + 1)) / FAIXAS) * fator),
    ),
    ponto: rgba(verdeClaro, 0.45 * fator),
    triangulo: rgba(acento, 0.55 * fator),
    pulso: CAUDA.map((_, k) => rgba(misturar(acento, texto, 0.35), [0.95, 0.45, 0.2][k] * fator)),
  };
}

export function NeuralBackground() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext('2d');
    // Sem canvas 2D (jsdom, navegador sem suporte): o fundo só fica sem a rede.
    if (!canvas || !ctx) return;

    const raiz = document.documentElement;
    const prng = criarPrng(SEMENTE + 1);
    const grade = criarGrade();
    const pulsos = criarPulsos();
    let paleta = montarPaleta(raiz);
    let rede: Rede = gerarRede(0, 0, SEMENTE);
    let distancia = 0;
    // Buffers do quadro, refeitos só quando a rede muda de tamanho.
    let segmentos: Float32Array[] = [];
    const contagem = new Int32Array(FAIXAS);
    let candidatos = new Int32Array(0);
    // Arestas no total do quadro (soma das faixas); também é o tamanho de candidatos.
    let capacidade = 0;
    let totalCandidatos = 0;

    let raf = 0;
    let ultimo: number | null = null;
    let tempo = 0;
    let proximoPulso = INTERVALO_PULSO_MIN_S;
    let visivel = true;
    const consulta = window.matchMedia?.(CONSULTA_MOVIMENTO_REDUZIDO);
    let reduzido = Boolean(consulta?.matches);
    let temporizador: ReturnType<typeof setTimeout> | undefined;

    function redimensionar() {
      const largura = canvas!.clientWidth || window.innerWidth;
      const altura = canvas!.clientHeight || window.innerHeight;
      if (largura === rede.largura && altura === rede.altura) return;
      const dpr = Math.min(window.devicePixelRatio || 1, DPR_MAXIMO);
      canvas!.width = Math.round(largura * dpr);
      canvas!.height = Math.round(altura * dpr);
      ctx!.setTransform(dpr, 0, 0, dpr, 0, 0);
      rede = gerarRede(largura, altura, SEMENTE);
      distancia = distanciaVizinho(largura, altura);
      capacidade = rede.n * ARESTAS_POR_NO;
      segmentos = Array.from({ length: FAIXAS }, () => new Float32Array(capacidade * 4));
      candidatos = new Int32Array(capacidade * 2);
      pulsos.ativo.fill(0);
    }

    // Definida uma vez: o laço de pares não cria função nem objeto por quadro.
    function registrarAresta(i: number, j: number, distancia2: number) {
      // Limite do total: a soma das faixas nunca passa de capacidade e candidatos não estoura.
      if (totalCandidatos >= capacidade) return;
      const proximidade = 1 - Math.sqrt(distancia2) / distancia;
      const faixa = Math.min(FAIXAS - 1, Math.floor(proximidade * FAIXAS));
      const k = contagem[faixa];
      const buffer = segmentos[faixa];
      if (k * 4 + 3 >= buffer.length) return;
      buffer[k * 4] = rede.x[i];
      buffer[k * 4 + 1] = rede.y[i];
      buffer[k * 4 + 2] = rede.x[j];
      buffer[k * 4 + 3] = rede.y[j];
      contagem[faixa] = k + 1;
      candidatos[totalCandidatos * 2] = i;
      candidatos[totalCandidatos * 2 + 1] = j;
      totalCandidatos++;
    }

    function desenhar() {
      const c = ctx!;
      c.clearRect(0, 0, rede.largura, rede.altura);
      contagem.fill(0);
      totalCandidatos = 0;
      if (rede.n > 0) {
        construirGrade(grade, rede, distancia);
        percorrerPares(grade, rede, distancia, registrarAresta);
      }

      c.lineWidth = 0.6;
      for (let f = 0; f < FAIXAS; f++) {
        if (contagem[f] === 0) continue;
        const buffer = segmentos[f];
        c.beginPath();
        for (let k = 0; k < contagem[f]; k++) {
          c.moveTo(buffer[k * 4], buffer[k * 4 + 1]);
          c.lineTo(buffer[k * 4 + 2], buffer[k * 4 + 3]);
        }
        c.strokeStyle = paleta.arestas[f];
        c.stroke();
      }

      c.beginPath();
      for (let i = 0; i < rede.n; i++) {
        if (rede.triangulo[i]) continue;
        c.moveTo(rede.x[i] + rede.tamanho[i], rede.y[i]);
        c.arc(rede.x[i], rede.y[i], rede.tamanho[i], 0, Math.PI * 2);
      }
      c.fillStyle = paleta.ponto;
      c.fill();

      c.beginPath();
      for (let i = 0; i < rede.n; i++) {
        if (!rede.triangulo[i]) continue;
        const r = rede.tamanho[i];
        const a = rede.angulo[i];
        for (let v = 0; v < 3; v++) {
          const angulo = a + (v * 2 * Math.PI) / 3;
          const vx = rede.x[i] + Math.cos(angulo) * r;
          const vy = rede.y[i] + Math.sin(angulo) * r;
          if (v === 0) c.moveTo(vx, vy);
          else c.lineTo(vx, vy);
        }
        c.closePath();
      }
      c.fillStyle = paleta.triangulo;
      c.fill();

      for (let k = 0; k < CAUDA.length; k++) {
        c.beginPath();
        let algum = false;
        for (let p = 0; p < pulsos.ativo.length; p++) {
          if (!pulsos.ativo[p]) continue;
          const t = pulsos.progresso[p] - CAUDA[k];
          if (t < 0) continue;
          const o = pulsos.origem[p];
          const d = pulsos.destino[p];
          const px = rede.x[o] + (rede.x[d] - rede.x[o]) * t;
          const py = rede.y[o] + (rede.y[d] - rede.y[o]) * t;
          const raio = k === 0 ? 1.8 : 1.3;
          c.moveTo(px + raio, py);
          c.arc(px, py, raio, 0, Math.PI * 2);
          algum = true;
        }
        if (algum) {
          c.fillStyle = paleta.pulso[k];
          c.fill();
        }
      }
    }

    function atualizar(dt: number) {
      tempo += dt;
      passo(rede, dt, tempo);
      avancarPulsos(pulsos, dt, DURACAO_PULSO_S);
      proximoPulso -= dt;
      if (proximoPulso <= 0) {
        proximoPulso =
          INTERVALO_PULSO_MIN_S + prng() * (INTERVALO_PULSO_MAX_S - INTERVALO_PULSO_MIN_S);
        if (totalCandidatos > 0) {
          const k = Math.floor(prng() * totalCandidatos);
          const a = candidatos[k * 2];
          const b = candidatos[k * 2 + 1];
          if (prng() < 0.5) iniciarPulso(pulsos, a, b);
          else iniciarPulso(pulsos, b, a);
        }
      }
    }

    function quadro(agora: number) {
      raf = requestAnimationFrame(quadro);
      if (ultimo === null) {
        // Primeiro quadro depois de iniciar ou retomar: sem passo, para não saltar.
        ultimo = agora;
        desenhar();
        return;
      }
      const decorrido = agora - ultimo;
      if (decorrido < QUADRO_MINIMO_MS) return;
      ultimo = agora;
      atualizar(Math.min(decorrido / 1000, DT_MAXIMO));
      desenhar();
    }

    function iniciar() {
      if (raf) return;
      ultimo = null;
      raf = requestAnimationFrame(quadro);
    }

    function parar() {
      if (raf) cancelAnimationFrame(raf);
      raf = 0;
      ultimo = null;
    }

    function avaliarLoop() {
      if (!document.hidden && visivel && !reduzido) {
        iniciar();
      } else {
        parar();
        // Com movimento reduzido fica um quadro estático em vez de tela vazia.
        if (reduzido) desenhar();
      }
    }

    function aoMudarVisibilidade() {
      avaliarLoop();
    }

    function aoMudarMovimento(evento: MediaQueryListEvent) {
      reduzido = evento.matches;
      avaliarLoop();
    }

    redimensionar();
    avaliarLoop();

    const observadorTamanho =
      typeof ResizeObserver === 'undefined'
        ? null
        : new ResizeObserver(() => {
            clearTimeout(temporizador);
            temporizador = setTimeout(() => {
              redimensionar();
              if (!raf) desenhar();
            }, ESPERA_REDIMENSIONAR_MS);
          });
    observadorTamanho?.observe(canvas);

    const observadorVisibilidade =
      typeof IntersectionObserver === 'undefined'
        ? null
        : new IntersectionObserver((entradas) => {
            visivel = entradas[entradas.length - 1]?.isIntersecting ?? true;
            avaliarLoop();
          });
    observadorVisibilidade?.observe(canvas);

    // A troca de modo (claro/escuro) muda as cores sem desmontar o componente.
    const observadorModo = new MutationObserver(() => {
      paleta = montarPaleta(raiz);
      if (!raf) desenhar();
    });
    observadorModo.observe(raiz, { attributes: true, attributeFilter: ['data-modo'] });

    document.addEventListener('visibilitychange', aoMudarVisibilidade);
    consulta?.addEventListener?.('change', aoMudarMovimento);

    return () => {
      parar();
      clearTimeout(temporizador);
      observadorTamanho?.disconnect();
      observadorVisibilidade?.disconnect();
      observadorModo.disconnect();
      document.removeEventListener('visibilitychange', aoMudarVisibilidade);
      consulta?.removeEventListener?.('change', aoMudarMovimento);
    };
  }, []);

  return <canvas ref={canvasRef} aria-hidden="true" style={ESTILO_CANVAS} />;
}

export default NeuralBackground;
