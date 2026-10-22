'use client';

import { useId } from 'react';
import { motion, useReducedMotion } from 'framer-motion';
import { M } from '@/lib/mensagens';
import type { FlashcardItem } from '@/types/novamente';

interface Props {
  item: FlashcardItem;
  virado: boolean;
  aoVirar: () => void;
}

/**
 * Cartão com flip 3D. O palco gira 180° e as duas faces ficam estáticas (0° e
 * 180°) com `backface-visibility: hidden`, então nunca há duas ou zero faces
 * visíveis. As duas faces permanecem no DOM e o palco tem altura fixa, então
 * virar não muda o layout.
 *
 * Com `prefers-reduced-motion` o palco não gira: a troca de face é instantânea
 * por opacidade (a face de trás vai para 0° para poder aparecer).
 */
export function FlashcardCard({ item, virado, aoVirar }: Props) {
  const prefereReduzido = useReducedMotion();
  // O hook pode devolver `null` no primeiro render; nesse caso seguimos com motion completo.
  const reduzido = prefereReduzido === true;
  const idFrente = useId();
  const idVerso = useId();

  return (
    // O `perspective` fica no wrapper: o palco é quem gira.
    <div className="relative h-[320px] w-full [perspective:1200px]">
      <motion.button
        type="button"
        onClick={aoVirar}
        aria-pressed={virado}
        aria-label={virado ? M.flashcards.mostrarFrente : M.flashcards.mostrarVerso}
        // O aria-label achataria o conteúdo; a face ativa é ligada como descrição.
        aria-describedby={virado ? idVerso : idFrente}
        data-testid="flashcard-palco"
        data-motion={reduzido ? 'reduzido' : 'completo'}
        // A preferência de motion só existe no cliente; o servidor sempre rende "completo".
        suppressHydrationWarning
        className="relative block h-full w-full text-left"
        style={{ transformStyle: 'preserve-3d' }}
        initial={false}
        animate={{ rotateY: virado && !reduzido ? 180 : 0 }}
        transition={{ duration: reduzido ? 0 : 0.45 }}
      >
        <span
          id={idFrente}
          aria-hidden={virado}
          data-ativa={!virado}
          suppressHydrationWarning
          className="absolute inset-0 block overflow-y-auto rounded-xl border bg-[var(--surface)] p-6"
          style={{
            transform: 'rotateY(0deg)',
            backfaceVisibility: 'hidden',
            opacity: reduzido && virado ? 0 : 1,
          }}
        >
          <span className="text-xs uppercase tracking-wide text-[var(--fg-muted)]">{M.flashcards.frente}</span>
          <span className="mt-3 block text-lg">{item.frente}</span>
        </span>

        <span
          id={idVerso}
          aria-hidden={!virado}
          data-ativa={virado}
          suppressHydrationWarning
          className="absolute inset-0 block overflow-y-auto rounded-xl border bg-[var(--surface-elevated)] p-6"
          style={{
            // No modo reduzido a face de trás precisa estar de frente para a troca por opacidade.
            transform: reduzido ? 'rotateY(0deg)' : 'rotateY(180deg)',
            backfaceVisibility: 'hidden',
            opacity: reduzido && !virado ? 0 : 1,
          }}
        >
          <span className="text-xs uppercase tracking-wide text-[var(--fg-muted)]">{M.flashcards.verso}</span>
          <span className="mt-3 block text-lg">{item.verso}</span>
        </span>
      </motion.button>
    </div>
  );
}
