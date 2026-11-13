import { Secao } from './Secao';
import { M } from '@/lib/mensagens';

export function Tecnologia() {
  return (
    <Secao id="tecnologia" titulo={M.landing.tecnologia.titulo} subtitulo={M.landing.tecnologia.subtitulo}>
      <ul className="grid gap-4 sm:grid-cols-2">
        {M.landing.tecnologia.itens.map((item) => (
          <li key={item.titulo} className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-6">
            <h3 className="font-semibold">{item.titulo}</h3>
            <p className="mt-2 text-sm leading-relaxed text-[var(--fg-muted)]">{item.texto}</p>
          </li>
        ))}
      </ul>
    </Secao>
  );
}
