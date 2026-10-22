'use client';

import { Download, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { useExport } from '@/features/adaptations/useExport';
import { M } from '@/lib/mensagens';
import type { AdaptacaoPacote } from '@/types/novamente';

export function ExportMenu({ pacote }: { pacote: AdaptacaoPacote }) {
  const { exportar, csvDisponivel, baixando, erro } = useExport(pacote);

  return (
    <div>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="outline" disabled={Boolean(baixando)}>
            {baixando ? (
              <Loader2 aria-hidden className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Download aria-hidden className="mr-2 h-4 w-4" />
            )}
            {M.resultado.exportar}
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem onSelect={() => exportar('md')}>Markdown</DropdownMenuItem>
          <DropdownMenuItem onSelect={() => exportar('pdf')}>PDF</DropdownMenuItem>
          <DropdownMenuItem
            disabled={!csvDisponivel}
            title={csvDisponivel ? undefined : M.resultado.csvIndisponivel}
            onSelect={() => exportar('csv')}
          >
            CSV (Anki)
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
      {erro && (
        <p role="alert" className="mt-2 text-sm text-[var(--danger)]">
          {erro}
        </p>
      )}
    </div>
  );
}
