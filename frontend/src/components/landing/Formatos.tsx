import { Secao } from './Secao';
import { M } from '@/lib/mensagens';

export function Formatos() {
  return (
    <Secao id="formatos" titulo={M.landing.formatos.titulo} subtitulo={M.landing.formatos.subtitulo}>
      <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {M.landing.formatos.itens.map((formato) => (
          <li key={formato.nome} className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-6">
            <h3 className="font-semibold">{formato.nome}</h3>
            <p className="mt-2 text-sm leading-relaxed text-[var(--fg-muted)]">{formato.descricao}</p>
          </li>
        ))}
      </ul>
    </Secao>
  );
}
