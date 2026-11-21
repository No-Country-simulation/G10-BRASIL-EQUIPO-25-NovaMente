'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { useApi } from '@/services/api/ApiProvider';
import { ErroApi, ErroContrato } from '@/services/api/erros';
import { LIMITES, RespostaChatSchema } from '@/types/schemas';
import type { MensagemChat, PerguntaChat, RespostaChat } from '@/types/novamente';

export type AlvoChat =
  | { tipo: 'aluno'; alunoId: string; materialId: string }
  | { tipo: 'empresa'; materialId: string };

export interface TurnoChat {
  id: number;
  pergunta: string;
  resposta: RespostaChat;
}

/** Histórico enviado ao servidor: só as últimas mensagens, cada uma dentro do limite. */
export function montarHistorico(turnos: TurnoChat[]): MensagemChat[] {
  const mensagens: MensagemChat[] = turnos.flatMap((turno) => [
    { papel: 'user' as const, conteudo: turno.pergunta.slice(0, LIMITES.chatConteudoMax) },
    { papel: 'assistant' as const, conteudo: turno.resposta.resposta.slice(0, LIMITES.chatConteudoMax) },
  ]);
  return mensagens.slice(-LIMITES.chatHistoricoMax);
}

/**
 * Conversa com o assistente de um material. Só os turnos concluídos entram no
 * histórico; se a chamada falha, a pergunta não é perdida (o chamador mantém o
 * texto no campo) e o erro fica disponível junto da espera do Retry-After.
 */
export function useChat(alvo: AlvoChat) {
  const api = useApi();
  const [turnos, setTurnos] = useState<TurnoChat[]>([]);
  const [pendente, setPendente] = useState<string | null>(null);
  const [erro, setErro] = useState<unknown>(null);
  const [espera, setEspera] = useState(0);
  const proximoId = useRef(1);
  // Descarta a resposta de uma conversa que já foi limpa. Ao trocar de material o
  // chamador remonta o componente (key), então o estado nasce zerado.
  const geracao = useRef(0);

  // Um único intervalo por espera: desconta 1 s por tick até zerar.
  const esperando = espera > 0;
  useEffect(() => {
    if (!esperando) return;
    const intervalo = setInterval(() => setEspera((atual) => Math.max(0, atual - 1)), 1000);
    return () => clearInterval(intervalo);
  }, [esperando]);

  const enviar = useCallback(
    async (pergunta: string, modelo?: string): Promise<boolean> => {
      const texto = pergunta.trim();
      if (!texto) return false;

      const minhaGeracao = geracao.current;
      const corpo: PerguntaChat = {
        pergunta: texto,
        historico: montarHistorico(turnos),
        ...(modelo ? { modelo } : {}),
      };

      setErro(null);
      setPendente(texto);
      try {
        const bruto =
          alvo.tipo === 'aluno'
            ? await api.perguntarAluno(alvo.alunoId, alvo.materialId, corpo)
            : await api.perguntarEmpresa(alvo.materialId, corpo);
        const analisado = RespostaChatSchema.safeParse(bruto);
        if (!analisado.success) {
          throw new ErroContrato(analisado.error.issues.map((i) => i.message).join('; '));
        }
        if (minhaGeracao !== geracao.current) return false;
        const id = proximoId.current++;
        setTurnos((atuais) => [...atuais, { id, pergunta: texto, resposta: analisado.data }]);
        setPendente(null);
        return true;
      } catch (falha) {
        if (minhaGeracao !== geracao.current) return false;
        setErro(falha);
        setPendente(null);
        if (falha instanceof ErroApi && falha.retryAfter) setEspera(falha.retryAfter);
        return false;
      }
    },
    [alvo, api, turnos],
  );

  const limpar = useCallback(() => {
    geracao.current += 1;
    setTurnos([]);
    setPendente(null);
    setErro(null);
    setEspera(0);
  }, []);

  return { turnos, pendente, erro, espera, enviar, limpar };
}
