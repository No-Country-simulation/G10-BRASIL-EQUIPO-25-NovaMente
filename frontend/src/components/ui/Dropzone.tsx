'use client';

import { useId, useState } from 'react';
import { UploadCloud, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { M } from '@/lib/mensagens';
import { formatarBytes } from '@/lib/formatadores';
import { cn } from '@/lib/cn';

interface Props {
  arquivo: File | null;
  aoSelecionar: (arquivo: File | null) => void;
  erro?: string;
  desabilitado?: boolean;
}

export function Dropzone({ arquivo, aoSelecionar, erro, desabilitado }: Props) {
  const [arrastando, setArrastando] = useState(false);
  const id = useId();
  const idErro = useId();

  return (
    <div>
      <div
        data-arrastando={arrastando}
        onDragOver={(e) => {
          e.preventDefault();
          if (!desabilitado) setArrastando(true);
        }}
        onDragLeave={() => setArrastando(false)}
        onDrop={(e) => {
          e.preventDefault();
          setArrastando(false);
          if (desabilitado) return;
          const escolhido = e.dataTransfer.files?.[0];
          if (escolhido) aoSelecionar(escolhido);
        }}
        className={cn(
          'flex min-h-[160px] flex-col items-center justify-center gap-2 rounded-lg border border-dashed p-6 text-center',
          'focus-within:ring-2 focus-within:ring-[var(--ring)]',
          arrastando && 'border-[var(--accent)] bg-[var(--accent-muted)]',
          erro && 'border-[var(--danger)]',
        )}
      >
        {arquivo ? (
          <div className="flex w-full items-center justify-between gap-3">
            <div className="text-left">
              <p className="text-sm font-medium break-all">{arquivo.name}</p>
              <p className="text-xs text-[var(--fg-muted)]">{formatarBytes(arquivo.size)}</p>
            </div>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => aoSelecionar(null)}
              disabled={desabilitado}
              className="h-11"
            >
              <X aria-hidden className="mr-1 h-4 w-4" />
              {M.formulario.removerArquivo}
            </Button>
          </div>
        ) : (
          <label htmlFor={id} className="flex cursor-pointer flex-col items-center gap-2">
            <UploadCloud aria-hidden className="h-6 w-6 text-[var(--accent)]" />
            <span className="text-sm">{M.formulario.dropzone}</span>
            <span className="text-xs text-[var(--fg-muted)]">{M.formulario.dropzoneAjuda}</span>
          </label>
        )}
        {/*
          Sem `accept`: o filtro nativo silenciaria um arquivo de extensão inválida
          sem dar retorno ao usuário. A validação (zod) é a fonte da mensagem.
        */}
        <input
          id={id}
          type="file"
          className="sr-only"
          disabled={desabilitado}
          aria-invalid={Boolean(erro)}
          aria-describedby={erro ? idErro : undefined}
          onChange={(e) => {
            const escolhido = e.target.files?.[0];
            // Permite escolher o mesmo arquivo novamente após remover.
            e.target.value = '';
            if (escolhido) aoSelecionar(escolhido);
          }}
        />
      </div>
      {erro && (
        <p id={idErro} role="alert" className="mt-2 text-sm text-[var(--danger)]">
          {erro}
        </p>
      )}
    </div>
  );
}
