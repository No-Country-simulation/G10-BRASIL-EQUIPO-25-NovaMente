'use client';

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
import type { Exportacao } from '@/features/adaptations/useExport';

export function ExportMenu({ exportacao }: { exportacao: Exportacao }) {
  const { exportar, csvDisponivel, baixando } = exportacao;

  const itemCsv = (
    <DropdownMenuItem disabled={!csvDisponivel} onSelect={() => exportar('csv')}>
      CSV (Anki)
    </DropdownMenuItem>
  );

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
          {csvDisponivel ? (
            itemCsv
          ) : (
            <TooltipProvider delayDuration={0}>
              <Tooltip>
                <TooltipTrigger asChild>
                  <span tabIndex={0} className="pointer-events-auto block">
                    {itemCsv}
                  </span>
                </TooltipTrigger>
                <TooltipContent side="left">{M.resultado.csvIndisponivel}</TooltipContent>
              </Tooltip>
            </TooltipProvider>
          )}
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
}
