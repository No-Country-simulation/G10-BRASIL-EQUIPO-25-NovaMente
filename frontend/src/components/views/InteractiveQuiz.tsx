'use client';

import { useEffect, useId, useRef, useState } from 'react';
import { CheckCircle2, XCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { M } from '@/lib/mensagens';
import { cn } from '@/lib/cn';
import type { QuizItem } from '@/types/novamente';

interface Resposta {
  item: number;
  escolhida: number;
  correta: boolean;
}

interface Props {
  itens: QuizItem[];
}

export function InteractiveQuiz({ itens }: Props) {
  const id = useId();
  const [indice, setIndice] = useState(0);
  const [selecionada, setSelecionada] = useState<number | null>(null);
  const [confirmada, setConfirmada] = useState(false);
  const [respostas, setRespostas] = useState<Resposta[]>([]);
  const [finalizado, setFinalizado] = useState(false);
  // Incrementado pelo "Refazer": garante foco no legend mesmo com uma única pergunta.
  const [recomecos, setRecomecos] = useState(0);
  const legendaRef = useRef<HTMLLegendElement>(null);
  const placarRef = useRef<HTMLHeadingElement>(null);

  const total = itens.length;
  // O quiz só recebe o recorte que usa; ainda assim, clampa para nunca sair dos itens.
  const posicao = Math.min(Math.max(indice, 0), Math.max(total - 1, 0));
  const item = itens[posicao];

  const acertos = respostas.filter((r) => r.correta).length;
  const erradas = respostas.filter((r) => !r.correta);
  const feedbackId = `quiz-feedback-${id}`;
  const perguntaId = `quiz-pergunta-${id}`;
  const anterior = useRef({ posicao, recomecos });

  useEffect(() => {
    // Não rouba foco na montagem: só quando a pergunta de fato muda (avanço ou refazer).
    const mudou = anterior.current.posicao !== posicao || anterior.current.recomecos !== recomecos;
    anterior.current = { posicao, recomecos };
    if (mudou) legendaRef.current?.focus();
  }, [posicao, recomecos]);

  useEffect(() => {
    if (finalizado) placarRef.current?.focus();
  }, [finalizado]);

  const reiniciar = () => {
    setIndice(0);
    setSelecionada(null);
    setConfirmada(false);
    setRespostas([]);
    setFinalizado(false);
    setRecomecos((n) => n + 1);
  };

  if (!item) {
    return (
      <section className="rounded-xl border border-dashed p-6 text-sm text-[var(--fg-muted)]">
        {M.quiz.vazio}
      </section>
    );
  }

  if (finalizado) {
    return (
      <section aria-labelledby={`quiz-placar-${id}`} className="space-y-6">
        <div className="rounded-xl border p-6 text-center">
          <h2
            id={`quiz-placar-${id}`}
            ref={placarRef}
            tabIndex={-1}
            className="text-sm uppercase tracking-wide text-[var(--fg-muted)]"
          >
            {M.quiz.placarRotulo}
          </h2>
          <p className="mt-2 text-4xl font-semibold">{M.quiz.placar(acertos, respostas.length)}</p>
          <Button className="mt-4" variant="outline" onClick={reiniciar}>
            {M.quiz.reiniciar}
          </Button>
        </div>

        <div>
          <h3 className="font-medium">{M.quiz.revisar}</h3>
          {erradas.length === 0 ? (
            <p className="mt-2 text-sm text-[var(--success)]">{M.quiz.semErros}</p>
          ) : (
            <ul className="mt-3 space-y-4">
              {erradas.map((r) => {
                const questao = itens[r.item];
                return (
                  <li key={r.item} className="rounded-lg border p-4 text-sm">
                    <p className="font-medium">{questao.pergunta}</p>
                    <p className="mt-2 text-[var(--danger)]">{M.quiz.suaResposta(questao.opcoes[r.escolhida])}</p>
                    <p className="text-[var(--success)]">
                      {M.quiz.respostaCorreta(questao.opcoes[questao.resposta_correta])}
                    </p>
                    <p className="mt-2 text-[var(--fg-muted)]">{questao.explicacao}</p>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      </section>
    );
  }

  const correta = selecionada === item.resposta_correta;

  return (
    <section aria-labelledby={perguntaId} className="space-y-5">
      <div className="flex items-center justify-between text-sm text-[var(--fg-muted)]">
        <span aria-live="polite">{M.quiz.contador(posicao + 1, total)}</span>
      </div>
      <Progress value={((posicao + 1) / total) * 100} aria-label={M.quiz.progresso} />

      <fieldset aria-describedby={confirmada ? feedbackId : undefined}>
        <legend
          id={perguntaId}
          ref={legendaRef}
          tabIndex={-1}
          className="rounded-sm text-lg font-medium focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[var(--ring)]"
        >
          {item.pergunta}
        </legend>
        <div className="mt-4 space-y-2">
          {item.opcoes.map((opcao, n) => {
            const marcada = selecionada === n;
            const respostaCerta = n === item.resposta_correta;
            return (
              <label
                key={`${posicao}-${n}`}
                className={cn(
                  'flex cursor-pointer items-center gap-3 rounded-lg border p-3 text-sm',
                  marcada && 'border-[var(--accent)] bg-[var(--accent-muted)]',
                  confirmada && respostaCerta && 'border-[var(--success)]',
                  confirmada && marcada && !correta && 'border-[var(--danger)]',
                  confirmada && 'cursor-default',
                )}
              >
                <input
                  type="radio"
                  name={`quiz-${id}-${posicao}`}
                  checked={marcada}
                  disabled={confirmada}
                  onChange={() => setSelecionada(n)}
                />
                <span>{opcao}</span>
                {confirmada && respostaCerta && (
                  <CheckCircle2 aria-hidden className="ml-auto h-4 w-4 text-[var(--success)]" />
                )}
                {confirmada && marcada && !correta && (
                  <XCircle aria-hidden className="ml-auto h-4 w-4 text-[var(--danger)]" />
                )}
              </label>
            );
          })}
        </div>
      </fieldset>

      <div id={feedbackId} aria-live="polite" aria-atomic="true" className="min-h-6 text-sm">
        {confirmada && (
          <div className={correta ? 'text-[var(--success)]' : 'text-[var(--danger)]'}>
            <p className="flex items-center gap-2 font-medium">
              {correta ? <CheckCircle2 aria-hidden className="h-4 w-4" /> : <XCircle aria-hidden className="h-4 w-4" />}
              {correta ? M.quiz.correto : M.quiz.incorreto}
            </p>
            <p className="mt-1 text-[var(--fg)]">{item.explicacao}</p>
          </div>
        )}
      </div>

      <div className="flex justify-end">
        {confirmada ? (
          <Button
            key="proxima"
            onClick={() => {
              if (posicao >= total - 1) {
                setFinalizado(true);
                return;
              }
              setIndice(posicao + 1);
              setSelecionada(null);
              setConfirmada(false);
            }}
          >
            {M.quiz.proxima}
          </Button>
        ) : (
          <Button
            key="confirmar"
            disabled={selecionada === null}
            onClick={() => {
              if (selecionada === null) return;
              setRespostas((r) => [
                ...r,
                { item: posicao, escolhida: selecionada, correta: selecionada === item.resposta_correta },
              ]);
              setConfirmada(true);
            }}
          >
            {M.quiz.confirmar}
          </Button>
        )}
      </div>
    </section>
  );
}
