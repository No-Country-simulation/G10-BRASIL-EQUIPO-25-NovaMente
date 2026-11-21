'use client';

import Link from 'next/link';
import { useEffect, useId, useRef, useState } from 'react';
import { ShieldCheck } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useConsentimento } from '@/features/privacidade/consentimento';
import { cn } from '@/lib/utils';
import { M } from '@/lib/mensagens';
import { ROTAS } from '@/lib/rotas';

const B = M.privacidade.banner;

interface InterruptorProps {
  marcado: boolean;
  aoAlternar: () => void;
  rotuloId: string;
  descricaoId: string;
}

/** Interruptor acessível (role="switch") com área de toque de 44 px. */
function Interruptor({ marcado, aoAlternar, rotuloId, descricaoId }: InterruptorProps) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={marcado}
      aria-labelledby={rotuloId}
      aria-describedby={descricaoId}
      onClick={aoAlternar}
      className="inline-flex h-11 w-14 shrink-0 items-center justify-center rounded-full outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--surface)]"
    >
      <span
        aria-hidden="true"
        className={cn(
          'relative block h-7 w-12 rounded-full border-2 transition-colors',
          marcado
            ? 'border-[var(--accent)] bg-[var(--accent)]'
            : 'border-[var(--fg-muted)] bg-transparent',
        )}
      >
        <span
          className={cn(
            'absolute top-1/2 block size-4 -translate-y-1/2 rounded-full transition-all',
            marcado ? 'left-6 bg-[var(--accent-fg)]' : 'left-1 bg-[var(--fg-muted)]',
          )}
        />
      </span>
    </button>
  );
}

/**
 * Aviso de cookies (LGPD). Aparece só para quem ainda não escolheu e pode ser
 * reaberto pelo rodapé ("Preferências de cookies"). As duas respostas têm o
 * mesmo peso visual, nada vem pré-marcado e recusar não bloqueia o uso.
 */
export function BannerCookies() {
  const { pronto, consentimento, decidido, painelAberto, decidir, fechar } = useConsentimento();
  const [personalizando, setPersonalizando] = useState(false);
  const [escolha, setEscolha] = useState<boolean | null>(null);
  const raiz = useRef<HTMLElement>(null);
  const idTitulo = useId();
  const idTexto = useId();
  const idPainel = useId();
  const idPreferencias = useId();
  const idPreferenciasDescricao = useId();

  const reaberto = decidido && painelAberto;
  const visivel = pronto && (!decidido || painelAberto);
  const painelVisivel = personalizando || reaberto;
  // Ao reabrir, o interruptor parte da escolha salva; no primeiro acesso, desligado.
  const preferencias = escolha ?? consentimento?.preferencias === true;

  useEffect(() => {
    if (reaberto) raiz.current?.focus();
  }, [reaberto]);

  if (!visivel) return null;

  const encerrar = () => {
    setPersonalizando(false);
    setEscolha(null);
  };

  const aoDecidir = (aceitaPreferencias: boolean) => {
    decidir(aceitaPreferencias);
    encerrar();
  };

  const aoVoltar = () => {
    if (reaberto) fechar();
    encerrar();
  };

  return (
    <section
      ref={raiz}
      tabIndex={-1}
      role="dialog"
      aria-modal="false"
      aria-labelledby={idTitulo}
      aria-describedby={idTexto}
      data-testid="banner-cookies"
      onKeyDown={(evento) => {
        if (evento.key === 'Escape' && reaberto) aoVoltar();
      }}
      className="fixed inset-x-0 bottom-0 z-[60] p-3 outline-none sm:p-4"
    >
      <div className="mx-auto max-h-[calc(100dvh-1.5rem)] w-full max-w-[960px] overflow-y-auto rounded-2xl border border-[var(--border-strong)] bg-[var(--surface-elevated)] p-4 text-[var(--fg)] shadow-[0_16px_56px_-12px_rgb(0_0_0/0.5)] sm:p-6">
        <div className="flex items-start gap-4">
          <span
            aria-hidden="true"
            className="hidden size-11 shrink-0 items-center justify-center rounded-xl bg-[var(--accent-muted)] text-[var(--fg)] sm:flex"
          >
            <ShieldCheck className="size-6" />
          </span>
          <div className="min-w-0">
            <h2 id={idTitulo} className="text-base font-semibold tracking-tight sm:text-lg">
              {B.titulo}
            </h2>
            <p id={idTexto} className="mt-2 text-sm leading-relaxed text-[var(--fg-muted)]">
              {B.texto} {B.mudarDeIdeia}{' '}
              <Link
                href={ROTAS.privacidade}
                className="font-medium text-[var(--fg)] underline underline-offset-4 hover:text-[var(--accent-hover)]"
              >
                {B.leiaPolitica}
              </Link>
              .
            </p>
          </div>
        </div>

        {painelVisivel ? (
          <div id={idPainel} className="mt-5 grid gap-3 border-t border-[var(--border)] pt-5">
            <h3 className="text-sm font-semibold">{B.painelTitulo}</h3>

            <div className="flex items-start justify-between gap-4 rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4">
              <div className="min-w-0">
                <p className="text-sm font-medium">{B.necessarios.titulo}</p>
                <p className="mt-1 text-sm leading-relaxed text-[var(--fg-muted)]">
                  {B.necessarios.descricao}
                </p>
              </div>
              <span className="shrink-0 rounded-full border border-[var(--border-strong)] px-3 py-1 text-xs font-medium">
                {B.necessarios.selo}
              </span>
            </div>

            <div className="flex items-start justify-between gap-4 rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4">
              <div className="min-w-0">
                <p id={idPreferencias} className="text-sm font-medium">
                  {B.preferencias.titulo}
                </p>
                <p
                  id={idPreferenciasDescricao}
                  className="mt-1 text-sm leading-relaxed text-[var(--fg-muted)]"
                >
                  {B.preferencias.descricao}
                </p>
              </div>
              <Interruptor
                marcado={preferencias}
                aoAlternar={() => setEscolha(!preferencias)}
                rotuloId={idPreferencias}
                descricaoId={idPreferenciasDescricao}
              />
            </div>

            <div className="flex flex-col gap-2 sm:flex-row sm:justify-end">
              <Button
                type="button"
                variant="secondary"
                onClick={aoVoltar}
                className="h-11 border-[var(--border-strong)] bg-[var(--surface)] px-5 text-sm text-[var(--fg)]"
              >
                {reaberto ? B.cancelar : B.voltar}
              </Button>
              <Button
                type="button"
                onClick={() => aoDecidir(preferencias)}
                className="h-11 bg-[var(--accent)] px-5 text-sm text-[var(--accent-fg)] hover:bg-[var(--accent-hover)]"
              >
                {B.salvar}
              </Button>
            </div>
          </div>
        ) : (
          <div className="mt-5 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-end">
            <Button
              type="button"
              variant="ghost"
              onClick={() => setPersonalizando(true)}
              className="h-11 px-4 text-sm text-[var(--fg)] underline underline-offset-4"
            >
              {B.personalizar}
            </Button>
            <Button
              type="button"
              variant="secondary"
              onClick={() => aoDecidir(false)}
              className="h-11 border-[var(--border-strong)] bg-[var(--surface)] px-5 text-sm text-[var(--fg)]"
            >
              {B.somenteNecessarios}
            </Button>
            <Button
              type="button"
              onClick={() => aoDecidir(true)}
              className="h-11 bg-[var(--accent)] px-5 text-sm text-[var(--accent-fg)] hover:bg-[var(--accent-hover)]"
            >
              {B.aceitar}
            </Button>
          </div>
        )}
      </div>
    </section>
  );
}
