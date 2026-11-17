import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Logo } from './Logo';
import { SkinSwitcher } from './SkinSwitcher';
import { TourLauncher } from './TourLauncher';
import { M } from '@/lib/mensagens';
import { ROTAS } from '@/lib/rotas';

const ANCORAS = [
  { href: '#como-funciona', rotulo: M.landing.header.comoFunciona },
  { href: '#formatos', rotulo: M.landing.header.formatos },
  { href: '#tecnologia', rotulo: M.landing.header.tecnologia },
  { href: '#equipe', rotulo: M.landing.header.equipe },
];

export function LandingHeader() {
  return (
    <header className="sticky top-0 z-40 border-b border-[var(--border)] bg-[var(--bg)]/90 backdrop-blur">
      <div className="mx-auto flex min-h-16 w-full max-w-[1120px] flex-wrap items-center justify-between gap-2 px-4 py-2 sm:px-6">
        <div className="flex items-center gap-8">
          <Logo />
          <nav aria-label={M.landing.header.navPrincipal} className="hidden items-center gap-5 text-sm lg:flex">
            {ANCORAS.map((ancora) => (
              <a key={ancora.href} href={ancora.href} className="text-[var(--fg-muted)] hover:text-[var(--fg)]">
                {ancora.rotulo}
              </a>
            ))}
          </nav>
        </div>
        <div className="flex items-center gap-2">
          <TourLauncher origem="landing" />
          <SkinSwitcher />
          <Link href={ROTAS.aluno} className="inline-flex h-11 items-center px-1 text-sm text-[var(--fg-muted)] hover:text-[var(--fg)]">
            {M.landing.header.souAluno}
          </Link>
          <Button
            asChild
            size="sm"
            className="h-11 bg-[var(--accent)] px-3 text-[var(--accent-fg)] hover:bg-[var(--accent-hover)]"
          >
            <Link href={ROTAS.empresaGerar}>{M.landing.header.areaEmpresa}</Link>
          </Button>
        </div>
      </div>
    </header>
  );
}
