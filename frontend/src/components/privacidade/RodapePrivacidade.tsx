import Link from 'next/link';
import { M } from '@/lib/mensagens';
import { ROTAS } from '@/lib/rotas';
import { cn } from '@/lib/utils';
import { BotaoPreferenciasCookies } from './BotaoPreferenciasCookies';

/** Links de privacidade para o rodapé das telas: política e preferências de cookies. */
export function RodapePrivacidade({ className }: { className?: string }) {
  return (
    <nav
      aria-label={M.privacidade.rodape.politica}
      className={cn('flex flex-wrap items-center gap-x-5 text-xs text-[var(--fg-muted)]', className)}
    >
      <Link
        href={ROTAS.privacidade}
        className="inline-flex min-h-11 items-center underline underline-offset-4 hover:text-[var(--fg)]"
      >
        {M.privacidade.rodape.politica}
      </Link>
      <BotaoPreferenciasCookies />
    </nav>
  );
}
