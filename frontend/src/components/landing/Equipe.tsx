import { ExternalLink } from 'lucide-react';
import { Secao } from './Secao';
import { M } from '@/lib/mensagens';

export function Equipe() {
  return (
    <Secao id="equipe" titulo={M.landing.equipe.titulo} subtitulo={M.landing.equipe.subtitulo}>
      <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {M.landing.equipe.integrantes.map((integrante) => (
          <li key={integrante.nome} className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-6">
            <h3 className="font-semibold">{integrante.nome}</h3>
            <p className="mt-1 text-sm text-[var(--fg-muted)]">{integrante.papel}</p>
          </li>
        ))}
      </ul>
      <div className="mt-8 flex flex-wrap items-center gap-4 text-sm">
        <a
          href={M.landing.equipe.repositorio}
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center gap-2 font-medium text-[var(--accent)] hover:text-[var(--accent-hover)]"
        >
          {M.landing.equipe.repositorioRotulo}
          <ExternalLink aria-hidden className="h-4 w-4" />
        </a>
        <p className="text-[var(--fg-muted)]">{M.landing.equipe.programa}</p>
      </div>
    </Secao>
  );
}
