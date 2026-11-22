import { LandingHeader } from '@/components/layout/LandingHeader';
import { M } from '@/lib/mensagens';
import { ComoFunciona } from './ComoFunciona';
import { Equipe } from './Equipe';
import { Footer } from './Footer';
import { Formatos } from './Formatos';
import { Hero } from './Hero';
import { Pedagogia } from './Pedagogia';
import { Problema } from './Problema';
import { Publicos } from './Publicos';
import { Tecnologia } from './Tecnologia';

export function LandingPage() {
  return (
    <div className="min-h-dvh bg-[var(--bg)] text-[var(--fg)]">
      <a
        href="#conteudo"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-[var(--accent)] focus:px-4 focus:py-2 focus:text-[var(--accent-fg)]"
      >
        {M.comum.irParaConteudo}
      </a>
      <LandingHeader />
      <main id="conteudo">
        <Hero />
        <Problema />
        <ComoFunciona />
        <Formatos />
        <Publicos />
        <Tecnologia />
        <Pedagogia />
        <Equipe />
      </main>
      <Footer />
    </div>
  );
}
