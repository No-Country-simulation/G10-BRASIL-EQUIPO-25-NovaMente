'use client';

import { LogOut } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { useAuthAtiva, useSair, useSessao } from '@/features/auth/useSessao';
import { M } from '@/lib/mensagens';

export function BotaoSair({ className }: { className?: string }) {
  const sair = useSair();

  return (
    <button
      type="button"
      disabled={sair.isPending}
      // Ao zerar a sessão, a guarda da área leva para a tela de entrada.
      onClick={() => sair.mutate()}
      className={
        className ??
        'inline-flex h-11 items-center gap-1.5 rounded-md px-2 text-sm text-[var(--fg-muted)] hover:text-[var(--fg)] disabled:opacity-50'
      }
    >
      <LogOut aria-hidden className="h-4 w-4" />
      {sair.isPending ? M.app.saindo : M.app.sair}
    </button>
  );
}

/**
 * Quem está logado + botão Sair. Some quando o login está desligado ou quando
 * não há sessão (modo aberto não mostra nada, como antes).
 */
export function MenuSessao() {
  const ativa = useAuthAtiva();
  const sessao = useSessao(ativa);

  if (!ativa || !sessao.data) return null;

  const rotulo = sessao.data.tipo === 'empresa' ? sessao.data.email : sessao.data.nome;

  return (
    <div className="flex items-center gap-1 sm:gap-2" data-testid="menu-sessao">
      <span className="hidden max-w-[180px] truncate text-sm font-medium sm:inline">{rotulo}</span>
      {sessao.data.demo && <Badge variant="secondary">{M.app.emDemonstracao}</Badge>}
      <BotaoSair />
    </div>
  );
}
