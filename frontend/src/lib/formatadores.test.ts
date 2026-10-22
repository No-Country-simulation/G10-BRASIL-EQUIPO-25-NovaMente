import { describe, expect, it } from 'vitest';
import {
  faixaAncoragem,
  formatarBytes,
  formatarDataRelativa,
  formatarPercentual,
  nomeArquivoExportacao,
  nomeArquivoPacote,
  slugify,
} from './formatadores';
import type { AdaptacaoPacote } from '@/types/novamente';

const pacote = {
  adaptacao_id: '01JAVCNFLCARD00000000001',
  documento: { titulo: 'Introdução à Arquitetura de Redes VCN — Ação & Cia' },
  metadados: { perfil_aplicado: 'LiderTecnico', formato_gerado: 'ResumoExecutivo' },
} as AdaptacaoPacote;

describe('slugify', () => {
  it('remove acentos e normaliza separadores', () => {
    expect(slugify('Introdução à Arquitetura de Redes VCN')).toBe('introducao-a-arquitetura-de-redes-vcn');
  });

  it('troca emoji e pontuação por hífen único e remove hífens das pontas', () => {
    expect(slugify('  🚀 VCN: o guia!!!  ')).toBe('vcn-o-guia');
  });

  it('limita a 60 caracteres sem terminar em hífen', () => {
    const s = slugify('palavra '.repeat(20));
    expect(s.length).toBeLessThanOrEqual(60);
    expect(s.endsWith('-')).toBe(false);
  });
});

describe('formatarBytes', () => {
  it('usa unidades binárias em pt-BR', () => {
    expect(formatarBytes(1024)).toBe('1 KB');
    expect(formatarBytes(10 * 1024 * 1024)).toBe('10 MB');
  });
});

describe('formatarPercentual', () => {
  it('converte 0..1 em porcentagem inteira', () => {
    expect(formatarPercentual(0.98)).toBe('98%');
    expect(formatarPercentual(0.945)).toBe('95%');
  });
});

describe('faixaAncoragem', () => {
  it('classifica nos limites', () => {
    expect(faixaAncoragem(0.9)).toBe('alta');
    expect(faixaAncoragem(0.89)).toBe('media');
    expect(faixaAncoragem(0.7)).toBe('media');
    expect(faixaAncoragem(0.69)).toBe('baixa');
  });
});

describe('formatarDataRelativa', () => {
  const agora = Date.parse('2026-10-21T15:02:11Z');

  it('usa minutos, horas e dias conforme a distância', () => {
    expect(formatarDataRelativa('2026-10-21T14:57:11Z', agora)).toBe('há 5 minutos');
    expect(formatarDataRelativa('2026-10-21T14:02:11Z', agora)).toBe('há 1 hora');
    expect(formatarDataRelativa('2026-10-18T15:02:11Z', agora)).toBe('há 3 dias');
  });

  it('descreve datas futuras', () => {
    expect(formatarDataRelativa('2026-10-21T17:02:11Z', agora)).toBe('em 2 horas');
  });
});

describe('nomeArquivoPacote e nomeArquivoExportacao', () => {
  it('usa slug do documento, perfil, formato e 8 caracteres do id', () => {
    expect(nomeArquivoExportacao(pacote, 'md')).toBe(
      'novamente-introducao-a-arquitetura-de-redes-vcn-acao-cia-lider-tecnico-resumo-executivo-01javcnf.md',
    );
    expect(nomeArquivoPacote(pacote)).toMatch(/^novamente-.*-01javcnf\.json$/);
  });

  it('não contém caractere inválido para cabeçalho HTTP', () => {
    expect(nomeArquivoExportacao(pacote, 'pdf')).toMatch(/^[a-z0-9.-]+$/);
  });
});
