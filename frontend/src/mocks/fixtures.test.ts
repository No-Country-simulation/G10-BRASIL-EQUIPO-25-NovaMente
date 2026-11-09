import { describe, expect, it } from 'vitest';
import { AdaptacaoPacoteSchema, MaterialResumoSchema } from '@/types/schemas';
import flashcards from './fixtures/flashcards-vcn-iniciante.json';
import materiais from './fixtures/materiais.json';
import quiz from './fixtures/quiz-vcn-desenvolvedor.json';
import tutorial from './fixtures/tutorial-vcn-lider.json';
import resumo from './fixtures/resumo-vcn-gestor.json';

describe('fixtures de demonstração', () => {
  it.each([
    ['flashcards', flashcards],
    ['quiz', quiz],
    ['tutorial', tutorial],
    ['resumo', resumo],
  ])('%s respeita o contrato AdaptacaoPacote', (_nome, fixture) => {
    const resultado = AdaptacaoPacoteSchema.safeParse(fixture);
    expect(resultado.success, resultado.success ? '' : JSON.stringify(resultado.error.issues)).toBe(true);
  });

  it.each(materiais.map((material) => [material.material_id, material]))(
    'material %s respeita o contrato MaterialResumo',
    (_id, material) => {
      const resultado = MaterialResumoSchema.safeParse(material);
      expect(
        resultado.success,
        resultado.success ? '' : JSON.stringify(resultado.error.issues),
      ).toBe(true);
    },
  );

  it('cobre os quatro formatos', () => {
    const formatos = [flashcards, quiz, tutorial, resumo].map(
      (p) => (p as { metadados: { formato_gerado: string } }).metadados.formato_gerado,
    );
    expect(new Set(formatos)).toEqual(new Set(['Flashcards', 'Quiz', 'Tutorial', 'ResumoExecutivo']));
  });
});
