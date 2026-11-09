'use client';

import Link from 'next/link';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { formatarDataRelativa } from '@/lib/formatadores';
import { M } from '@/lib/mensagens';
import { ROTAS } from '@/lib/rotas';
import type { AlunoResumo } from '@/types/novamente';

export interface AlunoCardProps {
  aluno: AlunoResumo;
  onEditar: (aluno: AlunoResumo) => void;
  onExcluir: (aluno: AlunoResumo) => void;
}

/**
 * Linha da lista de alunos. Em telas pequenas as células viram blocos, então a
 * mesma marcação responde como tabela no desktop e como card no mobile.
 */
export function AlunoCard({ aluno, onEditar, onExcluir }: AlunoCardProps) {
  const ativo = aluno.status === 'ativo';

  return (
    <tr className="mb-3 block rounded-xl border p-4 align-top md:mb-0 md:table-row md:rounded-none md:border-0 md:border-b md:p-0">
      <td className="block px-1 py-1 md:table-cell md:px-3 md:py-4">
        <span className="block text-xs font-medium uppercase tracking-wide text-[var(--fg-muted)] md:hidden">
          {M.alunos.colunaNome}
        </span>
        <span className="font-medium">{aluno.nome}</span>
      </td>

      <td className="block px-1 py-1 md:table-cell md:px-3 md:py-4">
        <span className="block text-xs font-medium uppercase tracking-wide text-[var(--fg-muted)] md:hidden">
          {M.alunos.colunaEmail}
        </span>
        <span className="break-all">{aluno.email}</span>
      </td>

      <td className="block px-1 py-1 md:table-cell md:px-3 md:py-4">
        <span className="block text-xs font-medium uppercase tracking-wide text-[var(--fg-muted)] md:hidden">
          {M.alunos.colunaStatus}
        </span>
        <Badge variant={ativo ? 'secondary' : 'outline'}>
          {ativo ? M.alunos.statusAtivo : M.alunos.statusInativo}
        </Badge>
      </td>

      <td className="block px-1 py-1 text-sm md:table-cell md:px-3 md:py-4">
        <span className="block text-xs font-medium uppercase tracking-wide text-[var(--fg-muted)] md:hidden">
          {M.alunos.colunaMateriais}
        </span>
        {M.alunos.totalMateriais(aluno.total_materiais)}
      </td>

      <td className="block px-1 py-1 text-sm text-[var(--fg-muted)] md:table-cell md:px-3 md:py-4">
        <span className="block text-xs font-medium uppercase tracking-wide text-[var(--fg-muted)] md:hidden">
          {M.alunos.colunaCriado}
        </span>
        {formatarDataRelativa(aluno.criado_em)}
      </td>

      <td className="mt-3 block px-1 md:mt-0 md:table-cell md:px-3 md:py-4 md:text-right">
        <div className="flex flex-wrap items-center gap-2 md:justify-end">
          <Button asChild variant="outline" size="sm">
            <Link href={ROTAS.empresaAluno(aluno.aluno_id)}>{M.alunos.materiais}</Link>
          </Button>
          <Button variant="ghost" size="sm" onClick={() => onEditar(aluno)}>
            {M.alunos.editar}
          </Button>
          <Button variant="destructive" size="sm" onClick={() => onExcluir(aluno)}>
            {M.alunos.excluir}
          </Button>
        </div>
      </td>
    </tr>
  );
}
