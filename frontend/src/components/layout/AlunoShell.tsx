import { RequerSessao } from '@/components/auth/RequerSessao';
import { AlunoHeader } from './AlunoHeader';
import { RodapePrivacidade } from '@/components/privacidade/RodapePrivacidade';
import { M } from '@/lib/mensagens';

export function AlunoShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-dvh bg-[var(--bg-pagina)] text-[var(--fg)]">
      <a
        href="#conteudo"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-[var(--accent)] focus:px-4 focus:py-2 focus:text-[var(--accent-fg)]"
      >
        {M.comum.irParaConteudo}
      </a>
      <AlunoHeader />
      <main id="conteudo" className="mx-auto max-w-[1280px] px-4 py-8">
        <RequerSessao perfil="aluno">{children}</RequerSessao>
      </main>
      <footer className="mx-auto max-w-[1280px] px-4 pb-3">
        <RodapePrivacidade />
      </footer>
    </div>
  );
}
