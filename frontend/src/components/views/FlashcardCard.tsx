'use client';

import { motion, useReducedMotion } from 'framer-motion';
import { M } from '@/lib/mensagens';
import type { FlashcardItem } from '@/types/novamente';

interface Props {
  item: FlashcardItem;
  virado: boolean;
  aoVirar: () => void;
}

/**
 * Cartão com flip 3D. As duas faces ficam sempre no DOM (a inativa só recebe
 * `aria-hidden`) e o palco tem altura fixa, então virar não muda o layout.
 *
 * Com `prefers-reduced-motion` o giro é trocado por uma troca instantânea de
 * face (opacidade via CSS), sem animação.
 */
export function FlashcardCard({ item, virado, aoVirar }: Props) {
  const prefereReduzido = useReducedMotion();
  // O hook pode devolver `null` no primeiro render; nesse caso seguimos com motion completo.
  const reduzido = prefereReduzido === true;

  return (
    <motion.button
      type="button"
      onClick={aoVirar}
      aria-pressed={virado}
      aria-label={virado ? M.flashcards.mostrarFrente : M.flashcards.mostrarVerso}
      data-testid="flashcard-palco"
      data-motion={reduzido ? 'reduzido' : 'completo'}
      // A preferência de motion só existe no cliente; o servidor sempre rende "completo".
      suppressHydrationWarning
      className="relative block h-[320px] w-full text-left [perspective:1200px]"
      style={{ transformStyle: 'preserve-3d' }}
    >
      <motion.span
        aria-hidden={virado}
        suppressHydrationWarning
        className="absolute inset-0 block overflow-y-auto rounded-xl border bg-[var(--surface)] p-6"
        style={{ backfaceVisibility: 'hidden', opacity: reduzido && virado ? 0 : 1 }}
        initial={false}
        animate={{ rotateY: !reduzido && virado ? 180 : 0 }}
        transition={{ duration: reduzido ? 0 : 0.45 }}
        data-ativa={!virado}
      >
        <span className="text-xs uppercase tracking-wide text-[var(--fg-muted)]">{M.flashcards.frente}</span>
        <span className="mt-3 block text-lg">{item.frente}</span>
      </motion.span>

      <motion.span
        aria-hidden={!virado}
        suppressHydrationWarning
        // A classe mantém a face traseira girada antes da hidratação; o `animate` inline vence depois.
        className="absolute inset-0 block overflow-y-auto rounded-xl border bg-[var(--surface-elevated)] p-6 [transform:rotateY(180deg)]"
        style={{ backfaceVisibility: 'hidden', opacity: reduzido && !virado ? 0 : 1 }}
        initial={false}
        animate={{ rotateY: reduzido ? 0 : 180 }}
        transition={{ duration: reduzido ? 0 : 0.45 }}
        data-ativa={virado}
      >
        <span className="text-xs uppercase tracking-wide text-[var(--fg-muted)]">{M.flashcards.verso}</span>
        <span className="mt-3 block text-lg">{item.verso}</span>
      </motion.span>
    </motion.button>
  );
}
