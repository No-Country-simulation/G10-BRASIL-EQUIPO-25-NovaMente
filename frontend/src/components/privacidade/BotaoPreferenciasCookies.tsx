'use client';

import { reabrirPreferenciasDeCookies } from '@/features/privacidade/consentimento';
import { cn } from '@/lib/utils';
import { M } from '@/lib/mensagens';

/** Reabre o aviso de cookies para quem quer rever ou revogar a escolha. */
export function BotaoPreferenciasCookies({ className }: { className?: string }) {
  return (
    <button
      type="button"
      onClick={reabrirPreferenciasDeCookies}
      className={cn(
        'inline-flex min-h-11 items-center text-left underline underline-offset-4 hover:text-[var(--fg)]',
        className,
      )}
    >
      {M.privacidade.rodape.preferencias}
    </button>
  );
}
