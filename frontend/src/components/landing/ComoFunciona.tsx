import { Secao } from './Secao';
import { M } from '@/lib/mensagens';

export function ComoFunciona() {
  return (
    <Secao id="como-funciona" titulo={M.landing.comoFunciona.titulo} subtitulo={M.landing.comoFunciona.subtitulo}>
      <ol className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {M.landing.comoFunciona.passos.map((passo, indice) => (
          <li key={passo.titulo} className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-6">
            <span
              aria-hidden
              className="grid h-8 w-8 place-items-center rounded-full bg-[var(--accent-muted)] text-sm font-semibold text-[var(--accent)]"
            >
              {indice + 1}
            </span>
            <h3 className="mt-4 font-semibold">{passo.titulo}</h3>
            <p className="mt-2 text-sm leading-relaxed text-[var(--fg-muted)]">{passo.texto}</p>
          </li>
        ))}
      </ol>
    </Secao>
  );
}
