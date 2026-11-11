'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useState } from 'react';
import { Menu, X } from 'lucide-react';
import { Logo } from './Logo';
import { SkinSwitcher } from './SkinSwitcher';
import { TourLauncher } from './TourLauncher';
import { M } from '@/lib/mensagens';
import { ROTAS } from '@/lib/rotas';
import { cn } from '@/lib/cn';

const NAV = [
  { href: ROTAS.empresaGerar, rotulo: M.app.navGerar },
  { href: ROTAS.empresaHistorico, rotulo: M.app.navHistorico },
  { href: ROTAS.empresaMateriais, rotulo: M.app.navMateriais },
  { href: ROTAS.empresaAlunos, rotulo: M.app.navAlunos },
];

function estaAtivo(caminho: string, href: string) {
  return caminho === href || caminho.startsWith(`${href}/`);
}

export function EmpresaHeader() {
  const caminho = usePathname();
  const [menuAberto, setMenuAberto] = useState(false);

  return (
    <header className="sticky top-0 z-40 border-b border-[var(--border)] bg-[var(--bg)]/90 backdrop-blur">
      <div className="mx-auto flex min-h-16 w-full max-w-[1280px] flex-wrap items-center justify-between gap-2 px-2 py-2 sm:px-4">
        <div className="flex items-center gap-2 sm:gap-8">
          <Logo />
          <nav aria-label={M.app.navPrincipal} data-tour="empresa-nav" className="hidden gap-1 md:flex">
            {NAV.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                aria-current={estaAtivo(caminho, item.href) ? 'page' : undefined}
                className={cn(
                  'rounded-md px-2 py-2 text-sm sm:px-3',
                  estaAtivo(caminho, item.href)
                    ? 'bg-[var(--accent-muted)] text-[var(--fg)]'
                    : 'text-[var(--fg-muted)] hover:text-[var(--fg)]',
                )}
              >
                {item.rotulo}
              </Link>
            ))}
          </nav>
        </div>
        <div className="flex items-center gap-2">
          <Link
            href={ROTAS.aluno}
            className="hidden text-sm text-[var(--fg-muted)] hover:text-[var(--fg)] md:inline"
          >
            {M.app.areaAluno}
          </Link>
          <TourLauncher origem="empresa" />
          <SkinSwitcher />
          <button
            type="button"
            aria-expanded={menuAberto}
            aria-controls="nav-empresa-mobile"
            aria-label={menuAberto ? M.app.fecharMenu : M.app.abrirMenu}
            onClick={() => setMenuAberto((aberto) => !aberto)}
            className="grid h-11 w-11 place-items-center rounded-md border border-[var(--border)] text-[var(--fg-muted)] hover:text-[var(--fg)] md:hidden"
          >
            {menuAberto ? <X aria-hidden className="h-5 w-5" /> : <Menu aria-hidden className="h-5 w-5" />}
          </button>
        </div>
      </div>
      {menuAberto && (
        <nav
          id="nav-empresa-mobile"
          aria-label={M.app.navMobile}
          className="border-t border-[var(--border)] px-2 py-2 md:hidden"
        >
          {NAV.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              onClick={() => setMenuAberto(false)}
              aria-current={estaAtivo(caminho, item.href) ? 'page' : undefined}
              className={cn(
                'block rounded-md px-3 py-2 text-sm',
                estaAtivo(caminho, item.href)
                  ? 'bg-[var(--accent-muted)] text-[var(--fg)]'
                  : 'text-[var(--fg-muted)] hover:text-[var(--fg)]',
              )}
            >
              {item.rotulo}
            </Link>
          ))}
          <Link
            href={ROTAS.aluno}
            onClick={() => setMenuAberto(false)}
            className="block rounded-md px-3 py-2 text-sm text-[var(--fg-muted)] hover:text-[var(--fg)]"
          >
            {M.app.areaAluno}
          </Link>
        </nav>
      )}
    </header>
  );
}
