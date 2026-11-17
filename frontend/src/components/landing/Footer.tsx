import Link from 'next/link';
import { M } from '@/lib/mensagens';
import { ROTAS } from '@/lib/rotas';

export function Footer() {
  return (
    <footer className="border-t border-[var(--border)] bg-[var(--surface)]">
      <div className="mx-auto flex w-full max-w-[1120px] flex-col gap-8 px-4 py-12 sm:px-6 md:flex-row md:justify-between">
        <div>
          <p className="font-semibold tracking-tight">{M.app.nome}</p>
          <p className="mt-2 max-w-sm text-sm text-[var(--fg-muted)]">{M.landing.equipe.programa}</p>
        </div>
        <nav aria-label={M.landing.footer.navegacao} className="flex flex-col gap-2 text-sm">
          <p className="font-medium">{M.landing.footer.navegacao}</p>
          <Link href={ROTAS.empresaGerar} className="text-[var(--fg-muted)] hover:text-[var(--fg)]">
            Gerar material
          </Link>
          <Link href={ROTAS.empresaHistorico} className="text-[var(--fg-muted)] hover:text-[var(--fg)]">
            Histórico
          </Link>
          <Link href={ROTAS.aluno} className="text-[var(--fg-muted)] hover:text-[var(--fg)]">
            Área do aluno
          </Link>
        </nav>
      </div>
      <div className="border-t border-[var(--border)]">
        <div className="mx-auto flex w-full max-w-[1120px] flex-col gap-2 px-4 py-6 text-xs text-[var(--fg-muted)] sm:px-6 md:flex-row md:items-center md:justify-between">
          <p>{M.landing.footer.creditos}</p>
          <p>{M.landing.footer.aviso}</p>
        </div>
      </div>
    </footer>
  );
}
