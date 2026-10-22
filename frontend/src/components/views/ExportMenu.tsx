'use client';

import { useId } from 'react';
import { Download, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { M } from '@/lib/mensagens';
import { cn } from '@/lib/cn';
import type { Exportacao } from '@/features/adaptations/useExport';

export function ExportMenu({ exportacao }: { exportacao: Exportacao }) {
  const { exportar, csvDisponivel, baixando } = exportacao;
  const idMotivoCsv = useId();

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
          <TooltipProvider delayDuration={0}>
            <Tooltip>
              <TooltipTrigger asChild>
                <DropdownMenuItem
                  aria-disabled={csvDisponivel ? undefined : true}
                  aria-describedby={csvDisponivel ? undefined : idMotivoCsv}
                  className={cn(!csvDisponivel && 'opacity-50')}
                  onSelect={(evento) => {
                    if (!csvDisponivel) {
                      evento.preventDefault();
                      return;
                    }
                    exportar('csv');
                  }}
                >
                  CSV (Anki)
                </DropdownMenuItem>
              </TooltipTrigger>
              {!csvDisponivel && <TooltipContent>{M.resultado.csvIndisponivel}</TooltipContent>}
            </Tooltip>
          </TooltipProvider>
        </DropdownMenuContent>
      </DropdownMenu>
      {!csvDisponivel && (
        <span id={idMotivoCsv} className="sr-only">
          {M.resultado.csvIndisponivel}
        </span>
      )}
    </div>
  );
}
