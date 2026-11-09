import { cn } from '@/lib/cn';

export function Secao({
  id,
  titulo,
  subtitulo,
  children,
  className,
}: {
  id: string;
  titulo: string;
  subtitulo?: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section
      id={id}
      aria-labelledby={`${id}-titulo`}
      className={cn('mx-auto w-full max-w-[1120px] px-4 py-16 sm:px-6', className)}
    >
      <div className="mb-10 max-w-2xl">
        <h2 id={`${id}-titulo`} className="text-2xl font-semibold tracking-tight sm:text-3xl">
          {titulo}
        </h2>
        {subtitulo && <p className="mt-3 text-[var(--fg-muted)]">{subtitulo}</p>}
      </div>
      {children}
    </section>
  );
}
