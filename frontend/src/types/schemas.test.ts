import { describe, expect, it } from 'vitest';
import {
  AdaptacaoInputSchema,
  AdaptacaoPacoteSchema,
  AdaptacaoUploadInputSchema,
  JobRespostaSchema,
  LIMITES,
  ApiProblemaSchema,
} from './schemas';

const pacoteBase = {
  adaptacao_id: '01JAVCNFLCARD00000000001',
  status: 'sucesso',
  criado_em: '2026-10-21T14:02:11Z',
  documento: { titulo: 'Introdução à VCN', origem: 'texto' },
  metadados: {
    perfil_aplicado: 'Iniciante',
    formato_gerado: 'Flashcards',
    nivel_detalhe_aplicado: 'Didatico',
    nicho_setor_aplicado: 'Geral',
    tempo_estimado_estudo_minutos: 5,
    conceitos_chave: ['VCN', 'Sub-redes'],
  },
  conteudo_adaptado: {
    tipo: 'flashcards',
    titulo: 'Dominando VCN',
    introducao_contextualizada: 'Imagine a VCN como um bairro privado.',
    itens: [
      { frente: 'O que é VCN?', verso: 'Rede virtual privada.' },
      { frente: 'O que é subnet?', verso: 'Subdivisão da VCN.' },
      { frente: 'O que é IGW?', verso: 'Porta de entrada da internet.' },
    ],
  },
  avaliacao_qualidade: { ancoragem_fonte_score: 0.98, clareza_pedagogica: 'Alta' },
  armazenamento_oci: { bucket: 'novamente', objeto_id: 'a.json', status_upload: 'concluido' },
};

const entradaValida = {
  documento_titulo: 'Introdução à VCN',
  documento_conteudo: 'a'.repeat(LIMITES.textoMin),
  perfil_destinatario: 'Iniciante',
  formato_saida: 'Flashcards',
  nicho_setor: 'Geral',
  nivel_detalhe: 'Didatico',
};

describe('AdaptacaoInputSchema', () => {
  it('aceita entrada válida e aplica trim no título', () => {
    const r = AdaptacaoInputSchema.parse({ ...entradaValida, documento_titulo: '  Introdução  ' });
    expect(r.documento_titulo).toBe('Introdução');
  });

  it('rejeita texto abaixo do mínimo e acima do máximo', () => {
    expect(AdaptacaoInputSchema.safeParse({ ...entradaValida, documento_conteudo: 'a'.repeat(199) }).success).toBe(false);
    expect(AdaptacaoInputSchema.safeParse({ ...entradaValida, documento_conteudo: 'a'.repeat(50_001) }).success).toBe(false);
  });

  it('conta caracteres, não bytes, em texto com acentos e emoji', () => {
    const texto = 'ã'.repeat(200);
    expect(AdaptacaoInputSchema.safeParse({ ...entradaValida, documento_conteudo: texto }).success).toBe(true);
    const comEmoji = '😀'.repeat(50_001);
    expect(AdaptacaoInputSchema.safeParse({ ...entradaValida, documento_conteudo: comEmoji }).success).toBe(false);
  });

  it('rejeita campo desconhecido', () => {
    expect(AdaptacaoInputSchema.safeParse({ ...entradaValida, extra: 1 }).success).toBe(false);
  });
});

const baseUpload = {
  documento_titulo: entradaValida.documento_titulo,
  perfil_destinatario: entradaValida.perfil_destinatario,
  formato_saida: entradaValida.formato_saida,
  nicho_setor: entradaValida.nicho_setor,
  nivel_detalhe: entradaValida.nivel_detalhe,
};

describe('AdaptacaoUploadInputSchema', () => {
  it('aceita arquivo .pdf pequeno', () => {
    const arquivo = new File(['conteudo'], 'manual.pdf', { type: 'application/pdf' });
    expect(AdaptacaoUploadInputSchema.safeParse({ ...baseUpload, arquivo }).success).toBe(true);
  });

  it('rejeita extensão não suportada, arquivo vazio e arquivo grande', () => {
    const docx = new File(['x'], 'manual.docx');
    const vazio = new File([''], 'manual.md');
    const grande = new File([new Uint8Array(LIMITES.arquivoMaxBytes + 1)], 'manual.pdf');
    expect(AdaptacaoUploadInputSchema.safeParse({ ...baseUpload, arquivo: docx }).success).toBe(false);
    expect(AdaptacaoUploadInputSchema.safeParse({ ...baseUpload, arquivo: vazio }).success).toBe(false);
    expect(AdaptacaoUploadInputSchema.safeParse({ ...baseUpload, arquivo: grande }).success).toBe(false);
  });
});

describe('AdaptacaoPacoteSchema', () => {
  it('aceita pacote coerente', () => {
    expect(AdaptacaoPacoteSchema.safeParse(pacoteBase).success).toBe(true);
  });

  it('rejeita tipo de conteúdo incompatível com o formato', () => {
    const r = AdaptacaoPacoteSchema.safeParse({
      ...pacoteBase,
      metadados: { ...pacoteBase.metadados, formato_gerado: 'Quiz' },
    });
    expect(r.success).toBe(false);
  });

  it('rejeita resposta_correta fora das opções', () => {
    const r = AdaptacaoPacoteSchema.safeParse({
      ...pacoteBase,
      metadados: { ...pacoteBase.metadados, formato_gerado: 'Quiz' },
      conteudo_adaptado: {
        tipo: 'quiz',
        titulo: 'Quiz VCN',
        introducao_contextualizada: 'Teste seus conhecimentos.',
        itens: [{ pergunta: 'P?', opcoes: ['a', 'b'], resposta_correta: 2, explicacao: 'porque' }],
      },
    });
    expect(r.success).toBe(false);
  });

  it('rejeita menos de 3 flashcards', () => {
    const r = AdaptacaoPacoteSchema.safeParse({
      ...pacoteBase,
      conteudo_adaptado: { ...pacoteBase.conteudo_adaptado, itens: pacoteBase.conteudo_adaptado.itens.slice(0, 2) },
    });
    expect(r.success).toBe(false);
  });
});

describe('JobRespostaSchema', () => {
  const jobBase = {
    job_id: 'j1',
    status: 'running',
    etapa_atual: 'extraindo',
    etapas_concluidas: [],
    progresso_percentual: 10,
    iniciado_em: '2026-10-21T14:02:11Z',
    atualizado_em: '2026-10-21T14:02:13Z',
  };

  it('aceita job em andamento', () => {
    expect(JobRespostaSchema.safeParse(jobBase).success).toBe(true);
  });

  it('exige resultado e adaptacao_id quando succeeded', () => {
    expect(JobRespostaSchema.safeParse({ ...jobBase, status: 'succeeded', etapa_atual: null }).success).toBe(false);
    expect(
      JobRespostaSchema.safeParse({
        ...jobBase,
        status: 'succeeded',
        etapa_atual: null,
        progresso_percentual: 100,
        adaptacao_id: pacoteBase.adaptacao_id,
        resultado: pacoteBase,
      }).success,
    ).toBe(true);
  });

  it('exige erro quando failed', () => {
    expect(JobRespostaSchema.safeParse({ ...jobBase, status: 'failed' }).success).toBe(false);
  });
});

describe('ApiProblemaSchema', () => {
  it('aceita erro com campos', () => {
    const r = ApiProblemaSchema.safeParse({
      erro: { codigo: 'VALIDACAO', mensagem: 'Dados inválidos', campos: { documento_titulo: 'Mínimo de 3' } },
    });
    expect(r.success).toBe(true);
  });

  it('rejeita código fora do contrato', () => {
    expect(ApiProblemaSchema.safeParse({ erro: { codigo: 'QUALQUER', mensagem: 'x' } }).success).toBe(false);
  });
});
