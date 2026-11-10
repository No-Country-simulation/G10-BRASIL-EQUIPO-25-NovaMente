'use client';

import Link from 'next/link';
import { SkinSwitcher } from './SkinSwitcher';
import { useIdentidadeAluno } from '@/features/aluno/useIdentidadeAluno';
import { M } from '@/lib/mensagens';
import { ROTAS } from '@/lib/rotas';

export function AlunoHeader() {
  const { aluno, trocarAluno } = useIdentidadeAluno();

  return (
    <header className="sticky top-0 z-40 border-b border-[var(--border)] bg-[var(--bg)]/90 backdrop-blur">
      <div className="mx-auto flex min-h-16 w-full max-w-[1280px] flex-wrap items-center justify-between gap-2 px-2 py-2 sm:px-4">
        <Link href={ROTAS.landing} className="font-semibold tracking-tight">
          {M.app.nome}
        </Link>
        <div className="flex items-center gap-2 sm:gap-3">
          {aluno && (
            <span className="max-w-[160px] truncate text-sm font-medium sm:max-w-none">
              {aluno.nome}
            </span>
          )}
          {aluno && (
            <Link
              href={ROTAS.aluno}
              onClick={trocarAluno}
              className="inline-flex h-11 items-center text-sm text-[var(--fg-muted)] hover:text-[var(--fg)]"
            >
              {M.app.trocarAluno}
            </Link>
          )}
          <SkinSwitcher />
          <Link
            href={ROTAS.empresaGerar}
            className="inline-flex h-11 items-center text-xs text-[var(--fg-muted)] hover:text-[var(--fg)] sm:text-sm"
          >
            {M.app.areaEmpresa}
          </Link>
        </div>
      </div>
    </header>
  );
}
