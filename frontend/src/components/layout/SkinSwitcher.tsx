'use client';

import { useSkin } from '@/features/theme/useSkin';
import { SKINS, type SkinId } from '@/themes/registry';
import { M } from '@/lib/mensagens';
import { cn } from '@/lib/cn';

export function SkinSwitcher() {
  const skin = useSkin((estado) => estado.skin);
  const setSkin = useSkin((estado) => estado.setSkin);

  return (
    <div role="group" aria-label={M.app.tema} className="flex items-center gap-1 rounded-full border p-1">
      {(Object.keys(SKINS) as SkinId[]).map((id) => (
        <button
          key={id}
          type="button"
          aria-pressed={skin === id}
          onClick={() => setSkin(id)}
          className={cn(
            // Abaixo de sm: botão redondo de 24 × 24 px com a cor do tema; a partir de sm, o rótulo de sempre.
            'grid h-6 w-6 place-items-center rounded-full text-xs transition-colors sm:block sm:h-auto sm:w-auto sm:px-3 sm:py-1',
            skin === id ? 'bg-[var(--accent)] text-[var(--accent-fg)]' : 'text-[var(--fg-muted)]',
          )}
        >
          <span
            aria-hidden="true"
            className="h-3.5 w-3.5 rounded-full border border-[var(--bg)] sm:hidden"
            style={{ backgroundColor: SKINS[id].cor }}
          />
          <span className="sr-only sm:not-sr-only">{SKINS[id].nome}</span>
        </button>
      ))}
    </div>
  );
}
