'use client';

import { Sparkles } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { CENARIOS } from '@/lib/constants';
import type { Cenario } from '@/features/adaptations/useAdaptationForm';
import { M } from '@/lib/mensagens';

export function Cenarios({
  aoDisparar,
  desabilitado,
}: {
  aoDisparar: (cenario: Cenario) => void;
  desabilitado?: boolean;
}) {
  return (
    <div>
      <p className="mb-2 text-xs uppercase tracking-wide text-[var(--fg-muted)]">{M.formulario.cenarios}</p>
      <div className="flex flex-wrap gap-2">
        {CENARIOS.map((cenario) => (
          <Button
            key={cenario.id}
            type="button"
            variant="outline"
            size="sm"
            disabled={desabilitado}
            onClick={() =>
              aoDisparar({
                titulo: cenario.titulo,
                perfil: cenario.perfil,
                formato: cenario.formato,
                nivel: cenario.nivel,
              })
            }
          >
            <Sparkles aria-hidden className="mr-2 h-3.5 w-3.5 text-[var(--accent)]" />
            {cenario.rotulo}
          </Button>
        ))}
      </div>
    </div>
  );
}
