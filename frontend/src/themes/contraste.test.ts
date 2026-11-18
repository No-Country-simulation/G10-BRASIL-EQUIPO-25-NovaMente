// @vitest-environment node
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

// Lê os tokens direto do CSS para o teste acompanhar qualquer ajuste de cor.
const CSS = readFileSync(fileURLToPath(new URL('./tokens.css', import.meta.url)), 'utf8');

type Rgb = [number, number, number];

function tokens(seletor: string): Record<string, string> {
  const inicio = CSS.indexOf(`${seletor} {`);
  if (inicio < 0) throw new Error(`Bloco ${seletor} não encontrado em tokens.css`);
  const bloco = CSS.slice(inicio, CSS.indexOf('}', inicio));
  return Object.fromEntries(
    [...bloco.matchAll(/(--[\w-]+):\s*([^;]+);/g)].map(([, nome, valor]) => [nome, valor.trim()]),
  );
}

function rgb(hex: string): Rgb {
  const limpo = hex.replace('#', '');
  return [0, 2, 4].map((i) => parseInt(limpo.slice(i, i + 2), 16)) as Rgb;
}

function luminancia([r, g, b]: Rgb): number {
  const canal = (c: number) => {
    const s = c / 255;
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * canal(r) + 0.7152 * canal(g) + 0.0722 * canal(b);
}

function contraste(a: Rgb, b: Rgb): number {
  const [claro, escuro] = [luminancia(a), luminancia(b)].sort((x, y) => y - x);
  return (claro + 0.05) / (escuro + 0.05);
}

/** Cor do fundo com o brilho por cima, no ponto mais forte (canto do gradiente). */
function comBrilho(fundo: Rgb, brilho: Rgb, alfa: number): Rgb {
  return fundo.map((c, i) => Math.round(c * (1 - alfa) + brilho[i] * alfa)) as Rgb;
}

const OLIVA: Rgb = [140, 170, 40];
const PETROLEO: Rgb = [20, 110, 120];

describe.each([
  ['dark', 1],
  ['light', 0.55],
])('skin neural, modo %s: contraste AA', (modo, opacidadeBrilho) => {
  const t = tokens(`[data-skin='neural'][data-modo='${modo}']`);
  const cor = (nome: string) => rgb(t[nome]);

  it.each([
    ['--fg', '--bg'],
    ['--fg', '--surface'],
    ['--fg', '--surface-elevated'],
    ['--fg-muted', '--bg'],
    ['--fg-muted', '--surface'],
    ['--fg-muted', '--surface-elevated'],
    ['--accent-fg', '--accent'],
    ['--accent-fg', '--accent-hover'],
    ['--accent', '--bg'],
    ['--accent', '--surface'],
    ['--danger', '--bg'],
  ])('texto %s sobre %s tem pelo menos 4,5:1', (texto, fundo) => {
    expect(contraste(cor(texto), cor(fundo))).toBeGreaterThanOrEqual(4.5);
  });

  it.each([
    ['--ring', '--bg'],
    ['--ring', '--surface'],
    ['--accent', '--surface-elevated'],
  ])('componente %s sobre %s tem pelo menos 3:1', (frente, fundo) => {
    expect(contraste(cor(frente), cor(fundo))).toBeGreaterThanOrEqual(3);
  });

  it.each([
    ['oliva', OLIVA, 0.14],
    ['azul-petróleo', PETROLEO, 0.12],
  ])('o texto continua AA sobre o brilho %s', (_nome, brilho, alfa) => {
    const fundo = comBrilho(cor('--bg'), brilho, alfa * opacidadeBrilho);
    for (const texto of ['--fg', '--fg-muted', '--accent']) {
      expect(contraste(cor(texto), fundo)).toBeGreaterThanOrEqual(4.5);
    }
  });
});
