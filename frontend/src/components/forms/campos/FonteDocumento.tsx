'use client';

import { useId } from 'react';
import type { UseFormReturn } from 'react-hook-form';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Dropzone } from '@/components/ui/Dropzone';
import type { Aba, ValoresFormulario } from '@/features/adaptations/useAdaptationForm';
import { LIMITES } from '@/types/schemas';
import { M } from '@/lib/mensagens';

export function FonteDocumento({
  form,
  aba,
  trocarAba,
  desabilitado,
}: {
  form: UseFormReturn<ValoresFormulario>;
  aba: Aba;
  trocarAba: (aba: Aba) => void;
  desabilitado?: boolean;
}) {
  const idTexto = useId();
  const idContador = useId();
  const idErroTexto = useId();
  const conteudo = form.watch('documento_conteudo') ?? '';
  const arquivo = form.watch('arquivo') ?? null;
  const erros = form.formState.errors;
  const totalCaracteres = Array.from(conteudo.trim()).length;

  return (
    <Tabs value={aba} onValueChange={(v) => trocarAba(v as Aba)}>
      <TabsList className="w-full group-data-horizontal/tabs:h-12">
        <TabsTrigger value="texto" className="h-11" disabled={desabilitado}>
          {M.formulario.abaTexto}
        </TabsTrigger>
        <TabsTrigger value="arquivo" className="h-11" disabled={desabilitado}>
          {M.formulario.abaArquivo}
        </TabsTrigger>
      </TabsList>

      <TabsContent value="texto">
        <label htmlFor={idTexto} className="mb-2 block text-sm font-medium">
          {M.formulario.campoTexto}
        </label>
        <textarea
          id={idTexto}
          rows={10}
          disabled={desabilitado}
          placeholder={M.formulario.placeholderTexto}
          aria-invalid={Boolean(erros.documento_conteudo)}
          aria-describedby={erros.documento_conteudo ? `${idContador} ${idErroTexto}` : idContador}
          className="w-full rounded-md border bg-[var(--surface)] p-3 text-sm"
          {...form.register('documento_conteudo')}
        />
        <div className="mt-1 flex items-center justify-between gap-3">
          {erros.documento_conteudo ? (
            <p id={idErroTexto} role="alert" className="text-sm text-[var(--danger)]">
              {erros.documento_conteudo.message}
            </p>
          ) : (
            <span />
          )}
          <p
            id={idContador}
            className={
              totalCaracteres > LIMITES.textoMax * 0.9
                ? 'text-xs text-[var(--warning)]'
                : 'text-xs text-[var(--fg-muted)]'
            }
          >
            {M.formulario.contador(totalCaracteres, LIMITES.textoMax)}
          </p>
        </div>
      </TabsContent>

      <TabsContent value="arquivo">
        <p className="mb-2 text-sm font-medium">{M.formulario.campoArquivo}</p>
        <Dropzone
          arquivo={arquivo}
          erro={erros.arquivo?.message}
          desabilitado={desabilitado}
          aoSelecionar={(novo) => form.setValue('arquivo', novo, { shouldValidate: true })}
        />
      </TabsContent>
    </Tabs>
  );
}
