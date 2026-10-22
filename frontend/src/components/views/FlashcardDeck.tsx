'use client';

import { useState } from 'react';
import { ArrowLeft, ArrowRight } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { FlashcardCard } from './FlashcardCard';
import { M } from '@/lib/mensagens';
import type { FlashcardItem } from '@/types/novamente';

interface Props {
  itens: FlashcardItem[];
}

export function FlashcardDeck({ itens }: Props) {
  const [indice, setIndice] = useState(0);
  const [virado, setVirado] = useState(false);

  const total = itens.length;
  const ultimo = total - 1;
  // O deck só recebe o recorte que usa; ainda assim, clampa para nunca sair dos itens.
  const indiceAtual = Math.min(Math.max(indice, 0), Math.max(ultimo, 0));
  const item = itens[indiceAtual];

  const irPara = (novo: number) => {
    if (novo < 0 || novo > ultimo) return;
    setIndice(novo);
    setVirado(false);
  };

  if (!item) {
    return (
      <section
        role="region"
        aria-label={M.flashcards.regiao(0)}
        className="rounded-xl border border-dashed p-6 text-sm text-[var(--fg-muted)]"
      >
        {M.flashcards.vazio}
      </section>
    );
  }

  return (
    <section
      role="region"
      aria-label={M.flashcards.regiao(total)}
      tabIndex={0}
      onKeyDown={(e) => {
        // preventDefault só quando a seta de fato navega; nas bordas o evento segue.
        if (e.key === 'ArrowRight' && indiceAtual < ultimo) {
          e.preventDefault();
          irPara(indiceAtual + 1);
        } else if (e.key === 'ArrowLeft' && indiceAtual > 0) {
          e.preventDefault();
          irPara(indiceAtual - 1);
        }
      }}
      className="space-y-4 rounded-xl focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[var(--ring)]"
    >
      <div className="flex items-center justify-between text-sm text-[var(--fg-muted)]">
        <span aria-live="polite">{M.flashcards.contador(indiceAtual + 1, total)}</span>
        <span>{M.flashcards.instrucao}</span>
      </div>

      <Progress value={((indiceAtual + 1) / total) * 100} aria-label={M.flashcards.progresso} />

      <FlashcardCard item={item} virado={virado} aoVirar={() => setVirado((v) => !v)} />

      {item.dica_didatica && (
        <p className="rounded-md border border-dashed p-3 text-sm text-[var(--fg-muted)]">
          <strong className="text-[var(--fg)]">{M.flashcards.dica}</strong>{' '}
          <span>{item.dica_didatica}</span>
        </p>
      )}

      <div className="flex justify-between">
        <Button variant="outline" onClick={() => irPara(indiceAtual - 1)} disabled={indiceAtual === 0}>
          <ArrowLeft aria-hidden className="mr-2 h-4 w-4" />
          {M.flashcards.anterior}
        </Button>
        <Button onClick={() => irPara(indiceAtual + 1)} disabled={indiceAtual === ultimo}>
          {M.flashcards.proximo}
          <ArrowRight aria-hidden className="ml-2 h-4 w-4" />
        </Button>
      </div>
    </section>
  );
}
