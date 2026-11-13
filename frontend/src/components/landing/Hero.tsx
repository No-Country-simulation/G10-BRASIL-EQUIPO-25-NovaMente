import Link from 'next/link';
import { ArrowRight } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { M } from '@/lib/mensagens';
import { ROTAS } from '@/lib/rotas';

export function Hero() {
  return (
    <section data-tour="landing-hero" aria-labelledby="landing-hero-titulo" className="relative overflow-hidden">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_top,var(--accent-muted),transparent_65%)]"
      />
      <div className="relative mx-auto flex w-full max-w-[1120px] flex-col items-start px-4 pb-20 pt-16 sm:px-6 sm:pt-24">
        <p className="rounded-full border border-[var(--border-strong)] px-3 py-1 text-xs font-medium text-[var(--fg-muted)]">
          {M.landing.hero.selo}
        </p>
        <h1
          id="landing-hero-titulo"
          className="mt-6 max-w-3xl text-4xl font-semibold tracking-tight sm:text-5xl lg:text-6xl"
        >
          {M.landing.hero.titulo}
        </h1>
        <p className="mt-5 max-w-2xl text-base leading-relaxed text-[var(--fg-muted)] sm:text-lg">
          {M.landing.hero.subtitulo}
        </p>
        <div className="mt-8 flex flex-wrap gap-3">
          <Button asChild size="lg" className="h-11 bg-[var(--accent)] px-5 text-[var(--accent-fg)] hover:bg-[var(--accent-hover)]">
            <Link href={ROTAS.empresaGerar}>
              {M.landing.hero.ctaEmpresa}
              <ArrowRight aria-hidden className="ml-2 h-4 w-4" />
            </Link>
          </Button>
          <Button asChild variant="outline" size="lg" className="h-11 px-5">
            <Link href={ROTAS.aluno}>{M.landing.hero.ctaAluno}</Link>
          </Button>
        </div>
      </div>
    </section>
  );
}
