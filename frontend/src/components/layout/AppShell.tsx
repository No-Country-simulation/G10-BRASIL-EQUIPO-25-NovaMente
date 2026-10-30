import { Header } from './Header';
import { HealthBanner } from './HealthBanner';
import { M } from '@/lib/mensagens';

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-dvh bg-[var(--bg)] text-[var(--fg)]">
      <a
        href="#conteudo"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-[var(--accent)] focus:px-4 focus:py-2 focus:text-[var(--accent-fg)]"
      >
        {M.comum.irParaConteudo}
      </a>
      <Header />
      <HealthBanner />
      <main id="conteudo" className="mx-auto max-w-[1280px] px-4 py-8">
        {children}
      </main>
    </div>
  );
}
