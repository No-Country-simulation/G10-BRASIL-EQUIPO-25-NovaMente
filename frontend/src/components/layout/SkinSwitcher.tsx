'use client';

import { useSkin } from '@/features/theme/useSkin';
import { SKINS, type SkinId } from '@/themes/registry';
import { cn } from '@/lib/cn';

export function SkinSwitcher() {
  const skin = useSkin((estado) => estado.skin);
  const setSkin = useSkin((estado) => estado.setSkin);

  return (
    <div role="group" aria-label="Tema" className="flex items-center gap-1 rounded-full border p-1">
      {(Object.keys(SKINS) as SkinId[]).map((id) => (
        <button
          key={id}
          type="button"
          aria-pressed={skin === id}
          onClick={() => setSkin(id)}
          className={cn(
            'rounded-full px-3 py-1 text-xs transition-colors',
            skin === id ? 'bg-[var(--accent)] text-[var(--accent-fg)]' : 'text-[var(--fg-muted)]',
          )}
        >
          {SKINS[id].nome}
        </button>
      ))}
    </div>
  );
}
