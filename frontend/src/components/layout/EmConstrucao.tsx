import { M } from '@/lib/mensagens';

export function EmConstrucao({ titulo }: { titulo: string }) {
  return (
    <section aria-labelledby="em-construcao-titulo" className="rounded-xl border border-dashed p-10 text-center">
      <p className="text-xs font-medium uppercase tracking-wide text-[var(--accent)]">{M.app.emConstrucao}</p>
      <h1 id="em-construcao-titulo" className="mt-2 text-2xl font-semibold">
        {titulo}
      </h1>
      <p className="mx-auto mt-3 max-w-md text-sm text-[var(--fg-muted)]">{M.app.emConstrucaoDescricao}</p>
    </section>
  );
}
