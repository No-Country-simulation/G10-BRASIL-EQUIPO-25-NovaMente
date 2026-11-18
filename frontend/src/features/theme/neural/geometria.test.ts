import { describe, expect, it } from 'vitest';
import {
  AREA_POR_NO,
  MAX_CLUSTERS,
  MAX_NOS,
  MAX_PULSOS,
  MIN_NOS,
  avancarPulsos,
  construirGrade,
  contarNos,
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

function paresPorGrade(rede: Rede, distancia: number): string[] {
  const grade = criarGrade();
  construirGrade(grade, rede, distancia);
  const pares: string[] = [];
  percorrerPares(grade, rede, distancia, (i, j) => pares.push(`${i}-${j}`));
  return pares.sort();
}

function paresPorForcaBruta(rede: Rede, distancia: number): string[] {
  const pares: string[] = [];
  for (let i = 0; i < rede.n; i++) {
    for (let j = i + 1; j < rede.n; j++) {
      const dx = rede.x[j] - rede.x[i];
      const dy = rede.y[j] - rede.y[i];
      if (dx * dx + dy * dy < distancia * distancia) pares.push(`${i}-${j}`);
    }
  }
  return pares.sort();
}

describe('contarNos', () => {
  it('é proporcional à área entre o mínimo e o teto', () => {
    expect(contarNos(1366, 768)).toBe(Math.round((1366 * 768) / AREA_POR_NO));
    expect(contarNos(375, 812)).toBe(MIN_NOS);
    expect(contarNos(3840, 2160)).toBe(MAX_NOS);
    expect(contarNos(375, 812)).toBeLessThan(contarNos(1366, 768));
  });

  it('não gera nós sem área', () => {
    expect(contarNos(0, 800)).toBe(0);
    expect(contarNos(800, Number.NaN)).toBe(0);
    expect(gerarRede(0, 0, 1).n).toBe(0);
  });
});

describe('gerarRede', () => {
  it('mesma semente gera o mesmo layout; semente diferente, outro', () => {
    const a = gerarRede(1280, 720, 42);
    const b = gerarRede(1280, 720, 42);
    const c = gerarRede(1280, 720, 43);
    expect(Array.from(a.x)).toEqual(Array.from(b.x));
    expect(Array.from(a.y)).toEqual(Array.from(b.y));
    expect(Array.from(a.triangulo)).toEqual(Array.from(b.triangulo));
    expect(Array.from(a.x)).not.toEqual(Array.from(c.x));
  });

  it('coloca todos os nós dentro da tela e tem alguns triângulos', () => {
    const rede = gerarRede(1280, 720, 7);
    for (let i = 0; i < rede.n; i++) {
      expect(rede.x[i]).toBeGreaterThanOrEqual(0);
      expect(rede.x[i]).toBeLessThanOrEqual(1280);
      expect(rede.y[i]).toBeGreaterThanOrEqual(0);
      expect(rede.y[i]).toBeLessThanOrEqual(720);
    }
    const triangulos = Array.from(rede.triangulo).filter(Boolean).length;
    expect(triangulos).toBeGreaterThan(0);
    expect(triangulos).toBeLessThan(rede.n / 3);
  });

  it('agrupa os nós: a maioria tem vizinhos próximos', () => {
    const rede = gerarRede(1600, 900, 11);
    const distancia = distanciaVizinho(1600, 900);
    const comVizinho = new Set(paresPorForcaBruta(rede, distancia).flatMap((p) => p.split('-')));
    expect(comVizinho.size).toBeGreaterThan(rede.n * 0.6);
    expect(MAX_CLUSTERS).toBeGreaterThanOrEqual(4);
  });
});

describe('criarPrng', () => {
  it('fica em [0, 1) e repete com a mesma semente', () => {
    const a = criarPrng(5);
    const b = criarPrng(5);
    for (let k = 0; k < 1000; k++) {
      const valor = a();
      expect(valor).toBe(b());
      expect(valor).toBeGreaterThanOrEqual(0);
      expect(valor).toBeLessThan(1);
    }
  });
});

describe('grade espacial', () => {
  it.each([
    [1280, 720, 3],
    [375, 812, 9],
    [2560, 1440, 21],
  ])('acha os mesmos vizinhos que a força bruta (%i × %i)', (largura, altura, semente) => {
    const rede = gerarRede(largura, altura, semente);
    const distancia = distanciaVizinho(largura, altura);
    const porGrade = paresPorGrade(rede, distancia);
    expect(porGrade.length).toBeGreaterThan(0);
    expect(porGrade).toEqual(paresPorForcaBruta(rede, distancia));
  });

  it('continua certa depois de mover os nós e reconstruir a mesma grade', () => {
    const rede = gerarRede(1280, 720, 5);
    const distancia = distanciaVizinho(1280, 720);
    const grade = criarGrade();
    for (let k = 0; k < 50; k++) {
      passo(rede, 0.5, k * 0.5);
      construirGrade(grade, rede, distancia);
      const pares: string[] = [];
      percorrerPares(grade, rede, distancia, (i, j) => pares.push(`${i}-${j}`));
      expect(pares.sort()).toEqual(paresPorForcaBruta(rede, distancia));
    }
  });
});

describe('passo', () => {
  it('mantém os nós dentro dos limites depois de muitos passos', () => {
    const rede = gerarRede(800, 600, 13);
    let t = 0;
    for (let k = 0; k < 5000; k++) {
      const dt = k % 500 === 0 ? 5 : 1 / 30; // inclui passos enormes, como depois de uma pausa
      t += dt;
      passo(rede, dt, t);
    }
    for (let i = 0; i < rede.n; i++) {
      expect(rede.x[i]).toBeGreaterThanOrEqual(0);
      expect(rede.x[i]).toBeLessThanOrEqual(800);
      expect(rede.y[i]).toBeGreaterThanOrEqual(0);
      expect(rede.y[i]).toBeLessThanOrEqual(600);
    }
  });

  it('é uma deriva lenta: poucos pixels em um segundo', () => {
    const rede = gerarRede(1280, 720, 17);
    const antesX = Float32Array.from(rede.x);
    const antesY = Float32Array.from(rede.y);
    for (let k = 1; k <= 30; k++) passo(rede, 1 / 30, k / 30);
    for (let i = 0; i < rede.n; i++) {
      expect(Math.hypot(rede.x[i] - antesX[i], rede.y[i] - antesY[i])).toBeLessThan(10);
    }
  });

  it('gira os triângulos devagar', () => {
    const rede = gerarRede(1280, 720, 19);
    const i = rede.triangulo.indexOf(1);
    const antes = rede.angulo[i];
    passo(rede, 1, 1);
    expect(Math.abs(rede.angulo[i] - antes)).toBeGreaterThan(0);
    expect(Math.abs(rede.angulo[i] - antes)).toBeLessThanOrEqual(0.15 + 1e-6);
  });
});

describe('pulsos', () => {
  it('avançam e são removidos ao chegar ao destino', () => {
    const pulsos = criarPulsos();
    expect(iniciarPulso(pulsos, 0, 1)).toBe(true);
    expect(avancarPulsos(pulsos, 0.5, 1)).toBe(1);
    expect(pulsos.progresso[0]).toBeCloseTo(0.5);
    expect(avancarPulsos(pulsos, 0.6, 1)).toBe(0);
    expect(pulsos.ativo[0]).toBe(0);
  });

  it(`não passam de ${MAX_PULSOS} ao mesmo tempo e reaproveitam o espaço livre`, () => {
    const pulsos = criarPulsos();
    for (let k = 0; k < MAX_PULSOS; k++) expect(iniciarPulso(pulsos, k, k + 1)).toBe(true);
    expect(iniciarPulso(pulsos, 0, 1)).toBe(false);
    avancarPulsos(pulsos, 2, 1);
    expect(iniciarPulso(pulsos, 3, 4)).toBe(true);
    expect(pulsos.origem[0]).toBe(3);
  });
});
