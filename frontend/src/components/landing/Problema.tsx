import { Secao } from './Secao';
import { M } from '@/lib/mensagens';

export function Problema() {
  return (
    <Secao id="problema" titulo={M.landing.problema.titulo} subtitulo={M.landing.problema.subtitulo}>
      <ul className="grid gap-4 md:grid-cols-3">
        {M.landing.problema.itens.map((item) => (
          <li key={item.titulo} className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-6">
            <h3 className="font-semibold">{item.titulo}</h3>
            <p className="mt-2 text-sm leading-relaxed text-[var(--fg-muted)]">{item.texto}</p>
          </li>
        ))}
      </ul>
    </Secao>
  );
}
