'use client';

import { useState } from 'react';
import { Dialog as DialogPrimitive } from 'radix-ui';
import { Button } from '@/components/ui/button';
import { M } from '@/lib/mensagens';
import { ErroApi, mensagemDoErro } from '@/services/api/erros';
import type { MaterialAtualizacao, MaterialResumo, VisibilidadeMaterial } from '@/types/novamente';

export interface MaterialEditDialogProps {
  material: MaterialResumo | null;
  open: boolean;
  onOpenChange: (aberto: boolean) => void;
  salvar: (dados: MaterialAtualizacao) => Promise<void>;
}

export function MaterialEditDialog({
  material,
  open,
  onOpenChange,
  salvar,
}: MaterialEditDialogProps) {
  const [titulo, setTitulo] = useState(material?.titulo ?? '');
  const [visibilidade, setVisibilidade] = useState<VisibilidadeMaterial>(
    material?.visibilidade ?? 'rascunho',
  );
  const [erroTitulo, setErroTitulo] = useState<string | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [salvando, setSalvando] = useState(false);

  if (!material) return null;

  const enviar = async (evento: React.FormEvent<HTMLFormElement>) => {
    evento.preventDefault();
    setErro(null);

    const limpo = titulo.trim();
    if (limpo.length < 3 || limpo.length > 150) {
      setErroTitulo(M.materiais.tituloInvalido);
      return;
    }
    setErroTitulo(null);

    const dados: MaterialAtualizacao = {};
    if (limpo !== material.titulo) dados.titulo = limpo;
    if (visibilidade !== material.visibilidade) dados.visibilidade = visibilidade;
    if (dados.titulo === undefined && dados.visibilidade === undefined) {
      onOpenChange(false);
      return;
    }

    setSalvando(true);
    try {
      await salvar(dados);
      onOpenChange(false);
    } catch (falha) {
      if (falha instanceof ErroApi) {
        const campos = falha.problema.erro.campos;
        if (campos?.titulo) {
          setErroTitulo(campos.titulo);
        } else {
          setErro(mensagemDoErro(falha));
        }
      } else {
        setErro(mensagemDoErro(falha));
      }
    } finally {
      setSalvando(false);
    }
  };

  return (
    <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-black/50" />
        <DialogPrimitive.Content className="fixed left-1/2 top-1/2 z-50 w-[min(92vw,480px)] -translate-x-1/2 -translate-y-1/2 rounded-xl border border-[var(--border)] bg-[var(--bg)] p-6 shadow-xl">
          <DialogPrimitive.Title className="text-lg font-semibold">
            {M.materiais.editarTitulo}
          </DialogPrimitive.Title>
          <DialogPrimitive.Description className="mt-1 text-sm text-[var(--fg-muted)]">
            {M.materiais.editarDescricao}
          </DialogPrimitive.Description>

          <form className="mt-5 space-y-4" onSubmit={enviar}>
            <div>
              <label htmlFor="material-titulo" className="text-sm font-medium">
                {M.materiais.campoTitulo}
              </label>
              <input
                id="material-titulo"
                value={titulo}
                onChange={(evento) => setTitulo(evento.target.value)}
                aria-invalid={erroTitulo ? true : undefined}
                aria-describedby={erroTitulo ? 'material-titulo-erro' : undefined}
                className="mt-1 h-10 w-full rounded-md border bg-[var(--surface)] px-3 text-sm"
              />
              {erroTitulo && (
                <p id="material-titulo-erro" role="alert" className="mt-1 text-sm text-[var(--danger)]">
                  {erroTitulo}
                </p>
              )}
            </div>

            <div>
              <label htmlFor="material-visibilidade" className="text-sm font-medium">
                {M.materiais.campoVisibilidade}
              </label>
              <select
                id="material-visibilidade"
                value={visibilidade}
                onChange={(evento) =>
                  setVisibilidade(evento.target.value as VisibilidadeMaterial)
                }
                className="mt-1 h-10 w-full rounded-md border bg-[var(--surface)] px-3 text-sm"
              >
                <option value="rascunho">{M.materiais.rascunho}</option>
                <option value="publicado">{M.materiais.publicado}</option>
              </select>
            </div>

            {erro && (
              <p role="alert" className="text-sm text-[var(--danger)]">
                {erro}
              </p>
            )}

            <div className="flex justify-end gap-2">
              <Button
                type="button"
                variant="outline"
                onClick={() => onOpenChange(false)}
                disabled={salvando}
              >
                {M.materiais.cancelar}
              </Button>
              <Button type="submit" disabled={salvando}>
                {salvando ? M.materiais.salvando : M.materiais.salvar}
              </Button>
            </div>
          </form>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}
