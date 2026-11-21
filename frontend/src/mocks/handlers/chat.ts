import { http, HttpResponse } from 'msw';
import { LIMITES, PerguntaChatSchema } from '@/types/schemas';
import type { AdaptacaoPacote, RespostaChat } from '@/types/novamente';
import {
  AlunoInativo,
  AlunoNaoEncontrado,
  MaterialNaoDisponivel,
  MaterialNaoEncontrado,
  obterMaterialAlunoMock,
  obterMaterialMock,
} from '../estadoCatalogo';

export const MODELOS_CHAT_MOCK = {
  padrao: 'google/gemma-4-31b-it',
  modelos: [
    'google/gemma-4-31b-it',
    'nvidia/nemotron-3.5-bolt-e4b',
    'nvidia/nemotron-3.5-lightning-30b-a3b',
  ],
};

const FRASE_RECUSA = 'Não encontrei isso no material.';

function erro(status: number, codigo: string, mensagem: string, extra: object = {}) {
  return HttpResponse.json({ erro: { codigo, mensagem, ...extra } }, { status });
}

function semAcento(texto: string): string {
  return texto.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
}

function trechosDoPacote(pacote: AdaptacaoPacote): string[] {
  const c = pacote.conteudo_adaptado;
  const trechos = [c.introducao_contextualizada];
  if (c.tipo === 'flashcards') {
    for (const item of c.itens) trechos.push(`${item.frente} ${item.verso}`);
  } else if (c.tipo === 'quiz') {
    for (const item of c.itens) trechos.push(`${item.pergunta} ${item.explicacao}`);
  } else {
    trechos.push(...c.itens.split(/\n{2,}/).filter((t) => t.trim().length > 0));
  }
  return trechos;
}

/** Resposta determinística: acha o trecho com mais palavras em comum com a pergunta. */
function responderDoPacote(pergunta: string, pacote: AdaptacaoPacote, modelo: string): RespostaChat {
  const palavras = new Set(
    semAcento(pergunta)
      .split(/[^a-z0-9]+/)
      .filter((p) => p.length >= 4),
  );
  let melhor = '';
  let melhorPontos = 0;
  for (const trecho of trechosDoPacote(pacote)) {
    const alvo = new Set(semAcento(trecho).split(/[^a-z0-9]+/));
    let pontos = 0;
    for (const p of palavras) if (alvo.has(p)) pontos += 1;
    if (pontos > melhorPontos) {
      melhorPontos = pontos;
      melhor = trecho;
    }
  }

  if (melhorPontos === 0) {
    return {
      resposta: FRASE_RECUSA,
      citacoes: [],
      base: 'pacote',
      recusou: true,
      fundamentada: false,
      ancoragem: null,
      modelo,
      trechos_usados: 0,
    };
  }

  const excerto = melhor.replace(/\s+/g, ' ').trim().slice(0, 240);
  return {
    resposta: `Segundo o material: ${excerto} [P1]`,
    citacoes: [{ id: 'P1', origem: 'pacote', excerto }],
    base: 'pacote',
    recusou: false,
    fundamentada: true,
    ancoragem: 0.92,
    modelo,
    trechos_usados: 1,
  };
}

// `carregarPacote` devolve o pacote ou a resposta de erro já pronta (404/403).
async function tratar(request: Request, carregarPacote: () => AdaptacaoPacote | Response) {
  let corpo: unknown;
  try {
    corpo = await request.json();
  } catch {
    return erro(422, 'VALIDACAO', 'Dados inválidos', { campos: { corpo: 'JSON inválido.' } });
  }

  const bruto = (corpo ?? {}) as { pergunta?: unknown };
  const texto = typeof bruto.pergunta === 'string' ? bruto.pergunta.trim() : '';
  if (texto === '') {
    return erro(422, 'PERGUNTA_VAZIA', 'Escreva uma pergunta.', {
      campos: { pergunta: 'A pergunta não pode ficar vazia.' },
    });
  }
  if (texto.length > LIMITES.chatPerguntaMax) {
    return erro(422, 'PERGUNTA_LONGA', 'A pergunta é longa demais.', {
      campos: { pergunta: `Use até ${LIMITES.chatPerguntaMax} caracteres.` },
    });
  }

  const analisado = PerguntaChatSchema.safeParse(corpo);
  if (!analisado.success) {
    return erro(422, 'VALIDACAO', 'Dados inválidos', {
      campos: Object.fromEntries(analisado.error.issues.map((i) => [i.path.join('.'), i.message])),
    });
  }

  const modelo = analisado.data.modelo ?? MODELOS_CHAT_MOCK.padrao;
  if (!MODELOS_CHAT_MOCK.modelos.includes(modelo)) {
    return erro(422, 'CHAT_MODELO_NAO_PERMITIDO', 'Modelo não permitido.', {
      detalhes: { modelos_permitidos: MODELOS_CHAT_MOCK.modelos },
    });
  }

  const pacote = carregarPacote();
  if (pacote instanceof Response) return pacote;
  return HttpResponse.json(responderDoPacote(texto, pacote, modelo));
}

export const handlersChat = [
  http.get('*/api/v1/chat/modelos', () => HttpResponse.json(MODELOS_CHAT_MOCK)),

  http.post('*/api/v1/aluno/materiais/:materialId/chat', ({ params, request }) => {
    const alunoId = new URL(request.url).searchParams.get('aluno_id');
    if (alunoId === null || alunoId === '') {
      return erro(422, 'VALIDACAO', 'Dados inválidos', { campos: { aluno_id: 'Informe o aluno.' } });
    }
    return tratar(request, () => {
      try {
        return obterMaterialAlunoMock(alunoId, String(params.materialId)).pacote;
      } catch (falha) {
        if (falha instanceof AlunoNaoEncontrado) {
          return erro(404, 'ALUNO_NAO_ENCONTRADO', 'Aluno não encontrado.');
        }
        if (falha instanceof AlunoInativo) return erro(403, 'ALUNO_INATIVO', 'Aluno inativo.');
        if (falha instanceof MaterialNaoDisponivel) {
          return erro(404, 'MATERIAL_NAO_DISPONIVEL', 'Material não disponível.');
        }
        throw falha;
      }
    });
  }),

  http.post('*/api/v1/materiais/:materialId/chat', ({ params, request }) =>
    tratar(request, () => {
      try {
        return obterMaterialMock(String(params.materialId)).pacote;
      } catch (falha) {
        if (falha instanceof MaterialNaoEncontrado) {
          return erro(404, 'MATERIAL_NAO_ENCONTRADO', 'Material não encontrado.');
        }
        throw falha;
      }
    }),
  ),
];
