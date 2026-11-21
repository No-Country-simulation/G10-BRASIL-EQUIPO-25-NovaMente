'use client';

import { useState } from 'react';
import { Check, Circle, Eye, EyeOff } from 'lucide-react';
import { avaliarSenha } from '@/lib/senha';
import { M } from '@/lib/mensagens';

export const CLASSE_CAMPO =
  'h-11 w-full rounded-md border bg-[var(--surface)] px-3 text-sm text-[var(--fg)] placeholder:text-[var(--fg-muted)]';

export interface CampoSenhaProps {
  id: string;
  rotulo: string;
  valor: string;
  onChange: (valor: string) => void;
  autoComplete: 'current-password' | 'new-password';
  /** Criação de senha: mostra a lista de requisitos que vai sendo marcada. */
  criacao?: boolean;
  invalido?: boolean;
  erro?: string | null;
}

/**
 * Campo de senha com mostrar/ocultar e a descrição do que é exigido, ligada ao
 * campo por `aria-describedby`. No login só descreve a regra; na criação,
 * confere cada requisito enquanto a pessoa digita.
 */
export function CampoSenha({
  id,
  rotulo,
  valor,
  onChange,
  autoComplete,
  criacao = false,
  invalido = false,
  erro,
}: CampoSenhaProps) {
  const [visivel, setVisivel] = useState(false);
  const ajudaId = `${id}-ajuda`;
  const erroId = `${id}-erro`;

  return (
    <div className="space-y-1.5">
      <label htmlFor={id} className="text-sm font-medium">
        {rotulo}
      </label>
      <div className="relative">
        <input
          id={id}
          type={visivel ? 'text' : 'password'}
          autoComplete={autoComplete}
          required
          value={valor}
          onChange={(evento) => onChange(evento.target.value)}
          aria-describedby={erro ? `${ajudaId} ${erroId}` : ajudaId}
          aria-invalid={invalido || undefined}
          className={`${CLASSE_CAMPO} pr-11`}
        />
        <button
          type="button"
          onClick={() => setVisivel((atual) => !atual)}
          aria-label={visivel ? M.entrar.senha.ocultar : M.entrar.senha.mostrar}
          className="absolute right-0 top-0 grid h-11 w-11 place-items-center text-[var(--fg-muted)] hover:text-[var(--fg)]"
        >
          {visivel ? <EyeOff aria-hidden className="h-4 w-4" /> : <Eye aria-hidden className="h-4 w-4" />}
        </button>
      </div>

      <div id={ajudaId} className="text-xs text-[var(--fg-muted)]">
        {criacao ? (
          <>
            <p>{M.entrar.senha.requisitosTitulo}</p>
            <ul className="mt-1 space-y-0.5">
              {avaliarSenha(valor).map((requisito) => (
                <li
                  key={requisito.id}
                  className={`flex items-center gap-1.5 ${requisito.atendido ? 'text-[var(--fg)]' : ''}`}
                >
                  {requisito.atendido ? (
                    <Check aria-hidden className="h-3.5 w-3.5" />
                  ) : (
                    <Circle aria-hidden className="h-3.5 w-3.5" />
                  )}
                  <span>{requisito.rotulo}</span>
                  <span className="sr-only">{requisito.atendido ? ' (atendido)' : ' (pendente)'}</span>
                </li>
              ))}
            </ul>
          </>
        ) : (
          <p>{M.entrar.senha.resumo}</p>
        )}
      </div>

      {erro && (
        <p id={erroId} role="alert" className="text-xs text-[var(--danger)]">
          {erro}
        </p>
      )}
    </div>
  );
}
