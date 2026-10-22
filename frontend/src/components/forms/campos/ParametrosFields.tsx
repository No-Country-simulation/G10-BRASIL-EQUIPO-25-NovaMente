'use client';

import { useId } from 'react';
import type { UseFormReturn } from 'react-hook-form';
import type { ValoresFormulario } from '@/features/adaptations/useAdaptationForm';
import { FORMATOS, NIVEIS, NICHOS, PERFIS } from '@/lib/constants';
import { M } from '@/lib/mensagens';
import { cn } from '@/lib/cn';

type Props = { form: UseFormReturn<ValoresFormulario> };

function Erro({ mensagem }: { mensagem?: string }) {
  if (!mensagem) return null;
  return (
    <p role="alert" className="mt-1 text-sm text-[var(--danger)]">
      {mensagem}
    </p>
  );
}

export function PerfilField({ form }: Props) {
  const atual = form.watch('perfil_destinatario');
  return (
    <fieldset>
      <legend className="mb-2 text-sm font-medium">{M.formulario.campoPerfil}</legend>
      <div className="grid gap-2 sm:grid-cols-2">
        {PERFIS.map((perfil) => (
          <label
            key={perfil.valor}
            className={cn(
              'min-h-11 cursor-pointer rounded-lg border p-3 text-sm',
              'focus-within:ring-2 focus-within:ring-[var(--ring)]',
              atual === perfil.valor && 'border-[var(--accent)] bg-[var(--accent-muted)]',
            )}
          >
            <input
              type="radio"
              value={perfil.valor}
              className="sr-only"
              {...form.register('perfil_destinatario')}
            />
            <span className="block font-medium">{perfil.rotulo}</span>
            <span className="block text-xs text-[var(--fg-muted)]">{perfil.descricao}</span>
          </label>
        ))}
      </div>
      <Erro mensagem={form.formState.errors.perfil_destinatario?.message} />
    </fieldset>
  );
}

export function FormatoField({ form }: Props) {
  const atual = form.watch('formato_saida');
  return (
    <fieldset>
      <legend className="mb-2 text-sm font-medium">{M.formulario.campoFormato}</legend>
      <div className="grid gap-2 sm:grid-cols-2">
        {FORMATOS.map((formato) => (
          <label
            key={formato.valor}
            className={cn(
              'min-h-11 cursor-pointer rounded-lg border p-3 text-sm',
              'focus-within:ring-2 focus-within:ring-[var(--ring)]',
              atual === formato.valor && 'border-[var(--accent)] bg-[var(--accent-muted)]',
            )}
          >
            <input
              type="radio"
              value={formato.valor}
              className="sr-only"
              {...form.register('formato_saida')}
            />
            <span className="block font-medium">{formato.rotulo}</span>
            <span className="block text-xs text-[var(--fg-muted)]">{formato.descricao}</span>
          </label>
        ))}
      </div>
      <Erro mensagem={form.formState.errors.formato_saida?.message} />
    </fieldset>
  );
}

export function NichoField({ form }: Props) {
  const id = useId();
  const idErro = useId();
  const erro = form.formState.errors.nicho_setor?.message;
  return (
    <div>
      <label htmlFor={id} className="mb-2 block text-sm font-medium">
        {M.formulario.campoNicho}
      </label>
      <select
        id={id}
        aria-invalid={Boolean(erro)}
        aria-describedby={erro ? idErro : undefined}
        className="h-11 w-full rounded-md border bg-[var(--surface)] px-3 text-sm"
        {...form.register('nicho_setor')}
      >
        {NICHOS.map((nicho) => (
          <option key={nicho.valor} value={nicho.valor}>
            {nicho.rotulo}
          </option>
        ))}
      </select>
      {erro && (
        <p id={idErro} role="alert" className="mt-1 text-sm text-[var(--danger)]">
          {erro}
        </p>
      )}
    </div>
  );
}

export function NivelField({ form }: Props) {
  const atual = form.watch('nivel_detalhe');
  return (
    <fieldset>
      <legend className="mb-2 text-sm font-medium">{M.formulario.campoNivel}</legend>
      <div className="flex rounded-md border p-1">
        {NIVEIS.map((nivel) => (
          <label
            key={nivel.valor}
            className={cn(
              'flex min-h-11 flex-1 cursor-pointer items-center justify-center rounded px-2 py-1.5 text-center text-sm',
              'focus-within:ring-2 focus-within:ring-[var(--ring)]',
              atual === nivel.valor && 'bg-[var(--accent)] text-[var(--accent-fg)]',
            )}
          >
            <input
              type="radio"
              value={nivel.valor}
              className="sr-only"
              {...form.register('nivel_detalhe')}
            />
            {nivel.rotulo}
          </label>
        ))}
      </div>
      <Erro mensagem={form.formState.errors.nivel_detalhe?.message} />
    </fieldset>
  );
}
