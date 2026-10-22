'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { SkinSwitcher } from './SkinSwitcher';
import { M } from '@/lib/mensagens';
import { cn } from '@/lib/cn';

const NAV = [
  { href: '/', rotulo: M.app.navGerar },
  { href: '/historico', rotulo: M.app.navHistorico },
];

export function Header() {
  const caminho = usePathname();

  return (
    <header className="sticky top-0 z-40 border-b border-[var(--border)] bg-[var(--bg)]/90 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-[1280px] items-center justify-between px-4">
        <div className="flex items-center gap-8">
          <Link href="/" className="font-semibold tracking-tight">
            {M.app.nome}
          </Link>
          <nav aria-label="Principal" className="flex gap-1">
            {NAV.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                aria-current={caminho === item.href ? 'page' : undefined}
                className={cn(
                  'rounded-md px-3 py-2 text-sm',
                  caminho === item.href
                    ? 'bg-[var(--accent-muted)] text-[var(--fg)]'
                    : 'text-[var(--fg-muted)] hover:text-[var(--fg)]',
                )}
              >
                {item.rotulo}
              </Link>
            ))}
          </nav>
        </div>
        <SkinSwitcher />
      </div>
    </header>
  );
}
