import Link from 'next/link';
import { Building2, GraduationCap } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Secao } from './Secao';
import { M } from '@/lib/mensagens';
import { ROTAS } from '@/lib/rotas';

export function Publicos() {
  return (
    <Secao
      id="publicos"
      titulo={M.landing.publicos.titulo}
      subtitulo={M.landing.publicos.subtitulo}
      className="scroll-mt-20"
    >
      <div data-tour="landing-publicos" className="grid gap-4 md:grid-cols-2">
        <article className="flex flex-col rounded-xl border border-[var(--border)] bg-[var(--surface)] p-8">
          <Building2 aria-hidden className="h-8 w-8 text-[var(--accent)]" />
          <h3 className="mt-4 text-xl font-semibold">{M.landing.publicos.empresa.titulo}</h3>
          <p className="mt-2 flex-1 text-sm leading-relaxed text-[var(--fg-muted)]">
            {M.landing.publicos.empresa.texto}
          </p>
          <Button
            asChild
            className="mt-6 h-11 w-fit bg-[var(--accent)] px-5 text-[var(--accent-fg)] hover:bg-[var(--accent-hover)]"
          >
            <Link href={ROTAS.empresaGerar}>{M.landing.publicos.empresa.cta}</Link>
          </Button>
        </article>
        <article className="flex flex-col rounded-xl border border-[var(--border)] bg-[var(--surface)] p-8">
          <GraduationCap aria-hidden className="h-8 w-8 text-[var(--accent)]" />
          <h3 className="mt-4 text-xl font-semibold">{M.landing.publicos.aluno.titulo}</h3>
          <p className="mt-2 flex-1 text-sm leading-relaxed text-[var(--fg-muted)]">
            {M.landing.publicos.aluno.texto}
          </p>
          <Button asChild variant="outline" className="mt-6 h-11 w-fit px-5">
            <Link href={ROTAS.aluno}>{M.landing.publicos.aluno.cta}</Link>
          </Button>
        </article>
      </div>
    </Secao>
  );
}
