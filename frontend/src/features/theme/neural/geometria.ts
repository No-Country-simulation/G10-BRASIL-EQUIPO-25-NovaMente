/**
 * Geometria do fundo animado da skin Neural: funções puras, sem DOM.
 *
 * Os dados ficam em typed arrays alocados só ao gerar a rede (ou ao crescer a
 * grade); nada aqui aloca por quadro. O layout vem de um PRNG com semente, então
 * a mesma semente e o mesmo tamanho de tela dão sempre a mesma rede.
 */

/** Área de tela (px² CSS) por nó; o total fica entre MIN_NOS e MAX_NOS. */
export const AREA_POR_NO = 18_000;
export const MIN_NOS = 30;
export const MAX_NOS = 90;
export const MIN_CLUSTERS = 4;
export const MAX_CLUSTERS = 6;
/** Fração dos nós espalhada fora dos clusters. */
export const FRACAO_SOLTOS = 0.15;
/** Fração dos nós desenhada como triângulo girando. */
export const FRACAO_TRIANGULOS = 0.12;
export const MAX_PULSOS = 6;

// Deriva: aceleração senoidal fraca, mola até a posição de origem e atrito.
const DERIVA = 3; // px/s²
const MOLA = 0.02; // 1/s²
const ATRITO = 0.6; // 1/s
const VELOCIDADE_MAXIMA = 8; // px/s

export type Prng = () => number;

/** PRNG mulberry32: rápido, 32 bits, suficiente para layout visual. */
export function criarPrng(semente: number): Prng {
  let a = semente >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4_294_967_296;
  };
}

/** Amostra da normal padrão (Box-Muller). */
export function gaussiana(prng: Prng): number {
  const u = Math.max(prng(), Number.EPSILON);
  return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * prng());
}

export function contarNos(largura: number, altura: number): number {
  if (!(largura > 0) || !(altura > 0)) return 0;
  const proporcional = Math.round((largura * altura) / AREA_POR_NO);
  return Math.min(MAX_NOS, Math.max(MIN_NOS, proporcional));
}

/** Distância máxima de uma aresta: menor em telas pequenas, para não virar teia. */
export function distanciaVizinho(largura: number, altura: number): number {
  return Math.min(150, Math.max(90, Math.min(largura, altura) * 0.18));
}

export interface Rede {
  n: number;
  largura: number;
  altura: number;
  x: Float32Array;
  y: Float32Array;
  vx: Float32Array;
  vy: Float32Array;
  ancoraX: Float32Array;
  ancoraY: Float32Array;
  fase: Float32Array;
  angulo: Float32Array;
  giro: Float32Array;
  tamanho: Float32Array;
  triangulo: Uint8Array;
}

function limitar(valor: number, minimo: number, maximo: number): number {
  return valor < minimo ? minimo : valor > maximo ? maximo : valor;
}

/** Centros espalhados pela tela (melhor de vários candidatos), longe uns dos outros. */
function centrosDosClusters(prng: Prng, total: number, largura: number, altura: number) {
  const centros: Array<[number, number]> = [];
  for (let c = 0; c < total; c++) {
    let melhor: [number, number] = [0, 0];
    let melhorDistancia = -1;
    for (let tentativa = 0; tentativa < 12; tentativa++) {
      const candidato: [number, number] = [
        largura * (0.1 + prng() * 0.8),
        altura * (0.1 + prng() * 0.8),
      ];
      let maisPerto = Infinity;
      for (const [cx, cy] of centros) {
        maisPerto = Math.min(maisPerto, (cx - candidato[0]) ** 2 + (cy - candidato[1]) ** 2);
      }
      if (maisPerto > melhorDistancia) {
        melhorDistancia = maisPerto;
        melhor = candidato;
      }
    }
    centros.push(melhor);
  }
  return centros;
}

export function gerarRede(largura: number, altura: number, semente: number): Rede {
  const prng = criarPrng(semente);
  const n = contarNos(largura, altura);
  const rede: Rede = {
    n,
    largura,
    altura,
    x: new Float32Array(n),
    y: new Float32Array(n),
    vx: new Float32Array(n),
    vy: new Float32Array(n),
    ancoraX: new Float32Array(n),
    ancoraY: new Float32Array(n),
    fase: new Float32Array(n),
    angulo: new Float32Array(n),
    giro: new Float32Array(n),
    tamanho: new Float32Array(n),
    triangulo: new Uint8Array(n),
  };
  if (n === 0) return rede;

  const totalClusters = MIN_CLUSTERS + Math.floor(prng() * (MAX_CLUSTERS - MIN_CLUSTERS + 1));
  const centros = centrosDosClusters(prng, totalClusters, largura, altura);
  const espalhamento = centros.map(() => Math.min(largura, altura) * (0.05 + prng() * 0.05));
  const soltos = Math.round(n * FRACAO_SOLTOS);

  for (let i = 0; i < n; i++) {
    let px: number;
    let py: number;
    if (i < soltos) {
      px = prng() * largura;
      py = prng() * altura;
    } else {
      const c = i % totalClusters;
      px = centros[c][0] + gaussiana(prng) * espalhamento[c];
      py = centros[c][1] + gaussiana(prng) * espalhamento[c];
    }
    rede.x[i] = rede.ancoraX[i] = limitar(px, 0, largura);
    rede.y[i] = rede.ancoraY[i] = limitar(py, 0, altura);
    rede.vx[i] = (prng() - 0.5) * 4;
    rede.vy[i] = (prng() - 0.5) * 4;
    rede.fase[i] = prng() * Math.PI * 2;
    rede.angulo[i] = prng() * Math.PI * 2;
    const triangulo = prng() < FRACAO_TRIANGULOS;
    rede.triangulo[i] = triangulo ? 1 : 0;
    rede.giro[i] = (0.05 + prng() * 0.1) * (prng() < 0.5 ? -1 : 1);
    rede.tamanho[i] = triangulo ? 2.5 + prng() * 1.5 : 0.8 + prng() * 1;
  }
  return rede;
}

/**
 * Avança a deriva em ``dt`` segundos (``t`` é o tempo total, que dá a direção
 * da deriva de cada nó). Os nós ricocheteiam nas bordas e nunca saem da tela.
 */
export function passo(rede: Rede, dt: number, t: number): void {
  const { n, largura, altura, x, y, vx, vy } = rede;
  const atrito = Math.max(0, 1 - ATRITO * dt);
  for (let i = 0; i < n; i++) {
    const ax = Math.cos(rede.fase[i] + t * 0.13) * DERIVA + (rede.ancoraX[i] - x[i]) * MOLA;
    const ay = Math.sin(rede.fase[i] * 1.3 + t * 0.11) * DERIVA + (rede.ancoraY[i] - y[i]) * MOLA;
    let nvx = (vx[i] + ax * dt) * atrito;
    let nvy = (vy[i] + ay * dt) * atrito;
    const velocidade = Math.hypot(nvx, nvy);
    if (velocidade > VELOCIDADE_MAXIMA) {
      nvx *= VELOCIDADE_MAXIMA / velocidade;
      nvy *= VELOCIDADE_MAXIMA / velocidade;
    }
    let nx = x[i] + nvx * dt;
    let ny = y[i] + nvy * dt;
    if (nx < 0) {
      nx = -nx;
      nvx = Math.abs(nvx);
    } else if (nx > largura) {
      nx = 2 * largura - nx;
      nvx = -Math.abs(nvx);
    }
    if (ny < 0) {
      ny = -ny;
      nvy = Math.abs(nvy);
    } else if (ny > altura) {
      ny = 2 * altura - ny;
      nvy = -Math.abs(nvy);
    }
    x[i] = limitar(nx, 0, largura);
    y[i] = limitar(ny, 0, altura);
    vx[i] = nvx;
    vy[i] = nvy;
    rede.angulo[i] += rede.giro[i] * dt;
  }
}

// ── Grade espacial ──────────────────────────────────────────────────────────

/**
 * Grade uniforme (counting sort por célula). Com a célula do tamanho da
 * distância de vizinhança, basta olhar a própria célula e as 8 vizinhas.
 */
export interface Grade {
  celula: number;
  colunas: number;
  linhas: number;
  inicio: Int32Array;
  cursor: Int32Array;
  itens: Int32Array;
  celulaDe: Int32Array;
}

export function criarGrade(): Grade {
  return {
    celula: 1,
    colunas: 0,
    linhas: 0,
    inicio: new Int32Array(1),
    cursor: new Int32Array(0),
    itens: new Int32Array(0),
    celulaDe: new Int32Array(0),
  };
}

export function construirGrade(grade: Grade, rede: Rede, celula: number): void {
  const colunas = Math.max(1, Math.ceil(rede.largura / celula));
  const linhas = Math.max(1, Math.ceil(rede.altura / celula));
  const total = colunas * linhas;
  // Só realoca quando a tela ou a rede crescem.
  if (grade.inicio.length < total + 1) grade.inicio = new Int32Array(total + 1);
  if (grade.cursor.length < total) grade.cursor = new Int32Array(total);
  if (grade.itens.length < rede.n) {
    grade.itens = new Int32Array(rede.n);
    grade.celulaDe = new Int32Array(rede.n);
  }
  grade.celula = celula;
  grade.colunas = colunas;
  grade.linhas = linhas;

  const { inicio, cursor, itens, celulaDe } = grade;
  inicio.fill(0, 0, total + 1);
  for (let i = 0; i < rede.n; i++) {
    const cx = limitar(Math.floor(rede.x[i] / celula), 0, colunas - 1);
    const cy = limitar(Math.floor(rede.y[i] / celula), 0, linhas - 1);
    const c = cy * colunas + cx;
    celulaDe[i] = c;
    inicio[c + 1]++;
  }
  for (let c = 0; c < total; c++) {
    inicio[c + 1] += inicio[c];
    cursor[c] = inicio[c];
  }
  for (let i = 0; i < rede.n; i++) {
    itens[cursor[celulaDe[i]]++] = i;
  }
}

/**
 * Chama ``visitar(i, j, d2)`` uma vez para cada par (i < j) a menos de
 * ``distancia``. A grade precisa ter sido construída com célula >= distância.
 */
export function percorrerPares(
  grade: Grade,
  rede: Rede,
  distancia: number,
  visitar: (i: number, j: number, distancia2: number) => void,
): void {
  const limite2 = distancia * distancia;
  const { colunas, linhas, inicio, itens, celulaDe } = grade;
  const { x, y } = rede;
  for (let i = 0; i < rede.n; i++) {
    const c = celulaDe[i];
    const cx = c % colunas;
    const cy = (c - cx) / colunas;
    for (let dy = -1; dy <= 1; dy++) {
      const ly = cy + dy;
      if (ly < 0 || ly >= linhas) continue;
      for (let dx = -1; dx <= 1; dx++) {
        const lx = cx + dx;
        if (lx < 0 || lx >= colunas) continue;
        const vizinha = ly * colunas + lx;
        for (let k = inicio[vizinha]; k < inicio[vizinha + 1]; k++) {
          const j = itens[k];
          if (j <= i) continue;
          const ddx = x[j] - x[i];
          const ddy = y[j] - y[i];
          const d2 = ddx * ddx + ddy * ddy;
          if (d2 < limite2) visitar(i, j, d2);
        }
      }
    }
  }
}

// ── Pulsos de sinal ─────────────────────────────────────────────────────────

/** Pool fixo de pulsos; cada um vai de ``origem`` a ``destino`` com progresso de 0 a 1. */
export interface Pulsos {
  origem: Int32Array;
  destino: Int32Array;
  progresso: Float32Array;
  ativo: Uint8Array;
}

export function criarPulsos(maximo: number = MAX_PULSOS): Pulsos {
  return {
    origem: new Int32Array(maximo),
    destino: new Int32Array(maximo),
    progresso: new Float32Array(maximo),
    ativo: new Uint8Array(maximo),
  };
}

/** Ocupa um espaço livre; devolve ``false`` se o pool estiver cheio. */
export function iniciarPulso(pulsos: Pulsos, origem: number, destino: number): boolean {
  for (let p = 0; p < pulsos.ativo.length; p++) {
    if (pulsos.ativo[p]) continue;
    pulsos.ativo[p] = 1;
    pulsos.origem[p] = origem;
    pulsos.destino[p] = destino;
    pulsos.progresso[p] = 0;
    return true;
  }
  return false;
}

/** Avança os pulsos ativos; os que chegam ao destino são liberados. Devolve quantos seguem ativos. */
export function avancarPulsos(pulsos: Pulsos, dt: number, duracao: number): number {
  let ativos = 0;
  for (let p = 0; p < pulsos.ativo.length; p++) {
    if (!pulsos.ativo[p]) continue;
    pulsos.progresso[p] += dt / duracao;
    if (pulsos.progresso[p] >= 1) {
      pulsos.ativo[p] = 0;
    } else {
      ativos++;
    }
  }
  return ativos;
}
