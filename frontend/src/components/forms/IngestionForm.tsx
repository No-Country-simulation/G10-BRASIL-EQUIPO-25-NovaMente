'use client';

import { useId } from 'react';
import { Button } from '@/components/ui/button';
import { useAdaptationForm } from '@/features/adaptations/useAdaptationForm';
import type { JobResposta } from '@/types/novamente';
import { LIMITES } from '@/types/schemas';
import { M } from '@/lib/mensagens';
import { FonteDocumento } from './campos/FonteDocumento';
import { FormatoField, NivelField, NichoField, PerfilField } from './campos/ParametrosFields';

export function IngestionForm({
  onCriado,
  desabilitado,
}: {
  onCriado: (job: JobResposta, repetir: () => Promise<JobResposta | null>) => void;
  desabilitado?: boolean;
}) {
  const { form, aba, trocarAba, enviar, enviando, erroGeral } = useAdaptationForm(onCriado, desabilitado);
  const idTitulo = useId();
  const idErroTitulo = useId();
  const erros = form.formState.errors;

  return (
    <form onSubmit={enviar} noValidate aria-label={M.formulario.titulo} className="space-y-6">
      {erroGeral && (
        <div role="alert" className="rounded-md border border-[var(--danger)] p-3 text-sm text-[var(--danger)]">
          {erroGeral}
        </div>
      )}

      <div>
        <label htmlFor={idTitulo} className="mb-2 block text-sm font-medium">
          {M.formulario.campoTitulo}
        </label>
        <input
          id={idTitulo}
          type="text"
          maxLength={LIMITES.tituloMax}
          disabled={desabilitado}
          placeholder={M.formulario.placeholderTitulo}
          aria-invalid={Boolean(erros.documento_titulo)}
          aria-describedby={erros.documento_titulo ? idErroTitulo : undefined}
          className="h-11 w-full rounded-md border bg-[var(--surface)] px-3 text-sm"
          {...form.register('documento_titulo')}
        />
        {erros.documento_titulo && (
          <p id={idErroTitulo} role="alert" className="mt-1 text-sm text-[var(--danger)]">
            {erros.documento_titulo.message}
          </p>
        )}
      </div>

      <FonteDocumento form={form} aba={aba} trocarAba={trocarAba} desabilitado={desabilitado} />
      <PerfilField form={form} desabilitado={desabilitado} />
      <FormatoField form={form} desabilitado={desabilitado} />
      <div className="grid gap-4 sm:grid-cols-2">
        <NichoField form={form} desabilitado={desabilitado} />
        <NivelField form={form} desabilitado={desabilitado} />
      </div>

      <Button type="submit" disabled={enviando || desabilitado} className="h-11 w-full">
        {enviando ? M.formulario.enviando : M.formulario.enviar}
      </Button>
    </form>
  );
}
