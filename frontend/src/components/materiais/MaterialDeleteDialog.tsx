'use client';

import { useState } from 'react';
import { Dialog as DialogPrimitive } from 'radix-ui';
import { Button } from '@/components/ui/button';
import { M } from '@/lib/mensagens';
import { mensagemDoErro } from '@/services/api/erros';
import type { MaterialResumo } from '@/types/novamente';

export interface MaterialDeleteDialogProps {
  material: MaterialResumo | null;
  open: boolean;
  onOpenChange: (aberto: boolean) => void;
  excluir: () => Promise<void>;
}

export function MaterialDeleteDialog({
  material,
  open,
  onOpenChange,
  excluir,
}: MaterialDeleteDialogProps) {
  const [excluindo, setExcluindo] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  if (!material) return null;

  const confirmar = async () => {
    setErro(null);
    setExcluindo(true);
    try {
      await excluir();
      onOpenChange(false);
    } catch (falha) {
      setErro(mensagemDoErro(falha));
    } finally {
      setExcluindo(false);
    }
  };

  return (
    <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-black/50" />
        <DialogPrimitive.Content className="fixed left-1/2 top-1/2 z-50 w-[min(92vw,440px)] -translate-x-1/2 -translate-y-1/2 rounded-xl border border-[var(--border)] bg-[var(--bg)] p-6 shadow-xl">
          <DialogPrimitive.Title className="text-lg font-semibold">
            {M.materiais.excluirTitulo}
          </DialogPrimitive.Title>
          <p className="mt-2 font-medium">{M.materiais.excluirConfirmacao(material.titulo)}</p>
          <DialogPrimitive.Description className="mt-2 text-sm text-[var(--fg-muted)]">
            {M.materiais.excluirDetalhe}
          </DialogPrimitive.Description>

          {erro && (
            <p role="alert" className="mt-3 text-sm text-[var(--danger)]">
              {erro}
            </p>
          )}

          <div className="mt-5 flex justify-end gap-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={excluindo}
            >
              {M.materiais.cancelar}
            </Button>
            <Button type="button" variant="destructive" onClick={confirmar} disabled={excluindo}>
              {excluindo ? M.materiais.excluindo : M.materiais.confirmarExclusao}
            </Button>
          </div>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}
