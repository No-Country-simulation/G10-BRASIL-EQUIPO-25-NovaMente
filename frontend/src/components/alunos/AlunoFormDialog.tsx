'use client';

import { zodResolver } from '@hookform/resolvers/zod';
import { useForm } from 'react-hook-form';
import { useState } from 'react';
import { z } from 'zod';
import { Dialog as DialogPrimitive } from 'radix-ui';
import { Button } from '@/components/ui/button';
import { M } from '@/lib/mensagens';
import { ErroApi, mensagemDoErro } from '@/services/api/erros';
import { emailAlunoSchema, nomeAlunoSchema, statusAlunoSchema } from '@/types/schemas';
import type { AlunoCriacao, AlunoResumo } from '@/types/novamente';

const AlunoFormSchema = z.object({
  nome: nomeAlunoSchema,
  email: emailAlunoSchema,
  status: statusAlunoSchema,
});

type ValoresAluno = z.infer<typeof AlunoFormSchema>;

export interface AlunoFormDialogProps {
  aluno?: AlunoResumo | null;
  open: boolean;
  onOpenChange: (aberto: boolean) => void;
  salvar: (dados: AlunoCriacao) => Promise<void>;
}

export function AlunoFormDialog({
  aluno = null,
  open,
  onOpenChange,
  salvar,
}: AlunoFormDialogProps) {
  const editando = aluno !== null;
  const [erroGeral, setErroGeral] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<ValoresAluno>({
    resolver: zodResolver(AlunoFormSchema),
    mode: 'onBlur',
    defaultValues: {
      nome: aluno?.nome ?? '',
      email: aluno?.email ?? '',
      status: aluno?.status ?? 'ativo',
    },
  });

  const enviar = handleSubmit(async (valores) => {
    setErroGeral(null);
    try {
      await salvar(valores);
      onOpenChange(false);
    } catch (falha) {
      if (falha instanceof ErroApi) {
        const campos = falha.problema.erro.campos;
        let mapeado = false;
        for (const campo of ['nome', 'email'] as const) {
          const mensagem = campos?.[campo];
          if (mensagem) {
            setError(campo, { type: 'server', message: mensagem });
            mapeado = true;
          }
        }
        if (falha.status === 409 || falha.problema.erro.codigo === 'EMAIL_JA_CADASTRADO') {
          setError('email', {
            type: 'server',
            message: campos?.email ?? falha.problema.erro.mensagem,
          });
          mapeado = true;
        }
        if (!mapeado) setErroGeral(mensagemDoErro(falha));
      } else {
        setErroGeral(mensagemDoErro(falha));
      }
    }
  });

  return (
    <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-black/50" />
        <DialogPrimitive.Content className="fixed left-1/2 top-1/2 z-50 w-[min(92vw,480px)] -translate-x-1/2 -translate-y-1/2 rounded-xl border border-[var(--border)] bg-[var(--bg)] p-6 shadow-xl">
          <DialogPrimitive.Title className="text-lg font-semibold">
            {editando ? M.alunos.editarTitulo : M.alunos.criarTitulo}
          </DialogPrimitive.Title>
          <DialogPrimitive.Description className="mt-1 text-sm text-[var(--fg-muted)]">
            {editando ? M.alunos.editarDescricao : M.alunos.criarDescricao}
          </DialogPrimitive.Description>

          <form className="mt-5 space-y-4" onSubmit={enviar} noValidate>
            <div>
              <label htmlFor="aluno-nome" className="text-sm font-medium">
                {M.alunos.campoNome}
              </label>
              <input
                id="aluno-nome"
                autoComplete="name"
                aria-invalid={errors.nome ? true : undefined}
                aria-describedby={errors.nome ? 'aluno-nome-erro' : undefined}
                className="mt-1 h-10 w-full rounded-md border bg-[var(--surface)] px-3 text-sm"
                {...register('nome')}
              />
              {errors.nome && (
                <p id="aluno-nome-erro" role="alert" className="mt-1 text-sm text-[var(--danger)]">
                  {errors.nome.message}
                </p>
              )}
            </div>

            <div>
              <label htmlFor="aluno-email" className="text-sm font-medium">
                {M.alunos.campoEmail}
              </label>
              <input
                id="aluno-email"
                type="email"
                autoComplete="email"
                aria-invalid={errors.email ? true : undefined}
                aria-describedby={errors.email ? 'aluno-email-erro' : undefined}
                className="mt-1 h-10 w-full rounded-md border bg-[var(--surface)] px-3 text-sm"
                {...register('email')}
              />
              {errors.email && (
                <p id="aluno-email-erro" role="alert" className="mt-1 text-sm text-[var(--danger)]">
                  {errors.email.message}
                </p>
              )}
            </div>

            <div>
              <label htmlFor="aluno-status" className="text-sm font-medium">
                {M.alunos.campoStatus}
              </label>
              <select
                id="aluno-status"
                className="mt-1 h-10 w-full rounded-md border bg-[var(--surface)] px-3 text-sm"
                {...register('status')}
              >
                <option value="ativo">{M.alunos.statusAtivo}</option>
                <option value="inativo">{M.alunos.statusInativo}</option>
              </select>
            </div>

            {erroGeral && (
              <p role="alert" className="text-sm text-[var(--danger)]">
                {erroGeral}
              </p>
            )}

            <div className="flex justify-end gap-2">
              <Button
                type="button"
                variant="outline"
                onClick={() => onOpenChange(false)}
                disabled={isSubmitting}
              >
                {M.alunos.cancelar}
              </Button>
              <Button type="submit" disabled={isSubmitting}>
                {isSubmitting ? M.alunos.salvando : M.alunos.salvar}
              </Button>
            </div>
          </form>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}
