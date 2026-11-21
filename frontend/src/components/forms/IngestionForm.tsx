'use client';

import { useId } from 'react';
import { Button } from '@/components/ui/button';
import { useAdaptationForm } from '@/features/adaptations/useAdaptationForm';
import type { JobResposta } from '@/types/novamente';
import { LIMITES } from '@/types/schemas';
import { M } from '@/lib/mensagens';
import { DOCUMENTO_DEMO } from '@/lib/constants';
import { Cenarios } from './Cenarios';
import { FonteDocumento } from './campos/FonteDocumento';
import { FormatoField, NivelField, NichoField, PerfilField } from './campos/ParametrosFields';

export function IngestionForm({
  onCriado,
  desabilitado,
  titulo,
}: {
  onCriado: (job: JobResposta, repetir: () => Promise<JobResposta | null>) => void;
  desabilitado?: boolean;
  /** Título da tela, exibido na mesma linha dos cenários de exemplo. */
  titulo?: React.ReactNode;
}) {
  const { form, aba, trocarAba, enviar, enviando, erroGeral, dispararCenario } = useAdaptationForm(onCriado, desabilitado);
  const idTitulo = useId();
  const idErroTitulo = useId();
  const erros = form.formState.errors;
  // Derivado do formState: some sozinho quando os erros (inclusive os do servidor) somem.
  const mostrarResumoErros = form.formState.submitCount > 0 && Object.keys(erros).length > 0;

  return (
    <form onSubmit={enviar} noValidate aria-label={M.formulario.titulo} className="flex flex-col gap-4 xl:h-full [@media(max-height:780px)]:xl:gap-3">
      <div className="flex shrink-0 flex-wrap items-center justify-between gap-x-6 gap-y-3">
        {titulo}
        <Cenarios
          aoDisparar={(cenario) => dispararCenario(cenario, DOCUMENTO_DEMO)}
          desabilitado={desabilitado || enviando}
        />
      </div>

      {erroGeral && (
        <div role="alert" className="shrink-0 rounded-md border border-[var(--danger)] p-3 text-sm text-[var(--danger)]">
          {erroGeral}
        </div>
      )}

      {/* Duas colunas a partir de md: documento à esquerda, parâmetros à direita. */}
      <div className="grid min-h-0 flex-1 gap-x-6 gap-y-5 md:grid-cols-2">
        <div className="flex min-h-0 flex-col gap-4">
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
        </div>

        <div className="flex min-h-0 flex-col gap-4 [@media(max-height:780px)]:xl:gap-3">
          <PerfilField form={form} desabilitado={desabilitado} />
          <FormatoField form={form} desabilitado={desabilitado} />
          <div className="grid gap-4 sm:grid-cols-[minmax(0,1fr)_minmax(0,1.25fr)]">
            <NichoField form={form} desabilitado={desabilitado} />
            <NivelField form={form} desabilitado={desabilitado} />
          </div>

          {mostrarResumoErros && (
            <div role="alert" className="rounded-md border border-[var(--danger)] p-3 text-sm text-[var(--danger)]">
              {M.formulario.resumoErros}
            </div>
          )}

          <Button type="submit" disabled={enviando || desabilitado} className="mt-auto h-11 w-full">
            {enviando ? M.formulario.enviando : M.formulario.enviar}
          </Button>
        </div>
      </div>
    </form>
  );
}
