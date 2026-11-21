'use client';

import { useEffect, useState } from 'react';
import { Button } from '@/components/ui/button';
import { M } from '@/lib/mensagens';
import { CLASSE_CAMPO } from './CampoSenha';

export const ESPERA_REENVIO_SEGUNDOS = 60;

/** Contagem regressiva do reenvio: um único intervalo enquanto houver espera. */
export function useEsperaReenvio() {
  const [espera, setEspera] = useState(0);
  const contando = espera > 0;

  useEffect(() => {
    if (!contando) return;
    const intervalo = setInterval(() => setEspera((atual) => Math.max(0, atual - 1)), 1000);
    return () => clearInterval(intervalo);
  }, [contando]);

  return { espera, iniciar: () => setEspera(ESPERA_REENVIO_SEGUNDOS), zerar: () => setEspera(0) };
}

export function Erro({ mensagem }: { mensagem: string | null }) {
  if (!mensagem) return null;
  return (
    <p role="alert" className="rounded-lg border border-[var(--danger)] px-3 py-2 text-sm text-[var(--danger)]">
      {mensagem}
    </p>
  );
}

export interface PassoCodigoProps {
  email: string;
  rotuloEnviar: string;
  rotuloEnviando: string;
  pendente: boolean;
  erro: string | null;
  espera: number;
  reenviando: boolean;
  onEnviar: (codigo: string) => void;
  onReenviar: () => void;
  onVoltar: () => void;
  /** Campos extras do passo (por exemplo, a senha nova no primeiro acesso). */
  children?: React.ReactNode;
  /** Condição extra para liberar o envio, além do código completo. */
  extraValido?: boolean;
}

/** Passo do código de 6 dígitos enviado por e-mail, igual para empresa e aluno. */
export function PassoCodigo({
  email,
  rotuloEnviar,
  rotuloEnviando,
  pendente,
  erro,
  espera,
  reenviando,
  onEnviar,
  onReenviar,
  onVoltar,
  children,
  extraValido = true,
}: PassoCodigoProps) {
  const [codigo, setCodigo] = useState('');

  return (
    <form
      className="space-y-4"
      onSubmit={(evento) => {
        evento.preventDefault();
        onEnviar(codigo);
      }}
    >
      <p className="text-sm" role="status">
        {M.entrar.codigo.enviadoPara(email)}
      </p>
      <div className="space-y-1.5">
        <label htmlFor="codigo-verificacao" className="text-sm font-medium">
          {M.entrar.codigo.campo}
        </label>
        <input
          id="codigo-verificacao"
          type="text"
          inputMode="numeric"
          autoComplete="one-time-code"
          pattern="\d{6}"
          maxLength={6}
          required
          autoFocus
          value={codigo}
          onChange={(evento) => setCodigo(evento.target.value.replace(/\D/g, ''))}
          className={`${CLASSE_CAMPO} text-center text-lg tracking-[0.4em]`}
        />
        <p className="text-xs text-[var(--fg-muted)]">{M.entrar.codigo.validade}</p>
        <p className="text-xs text-[var(--fg-muted)]">{M.entrar.codigo.spam}</p>
      </div>

      {children}

      <Erro mensagem={erro} />
      <Button
        type="submit"
        className="h-11 w-full"
        disabled={pendente || codigo.length !== 6 || !extraValido}
      >
        {pendente ? rotuloEnviando : rotuloEnviar}
      </Button>
      <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
        <button
          type="button"
          disabled={espera > 0 || reenviando}
          onClick={onReenviar}
          className="inline-flex h-11 items-center text-[var(--accent)] hover:underline disabled:text-[var(--fg-muted)] disabled:no-underline"
        >
          {espera > 0 ? M.entrar.codigo.reenviarEm(espera) : M.entrar.codigo.reenviar}
        </button>
        <button
          type="button"
          onClick={onVoltar}
          className="inline-flex h-11 items-center text-[var(--fg-muted)] hover:text-[var(--fg)]"
        >
          {M.entrar.codigo.voltar}
        </button>
      </div>
    </form>
  );
}
