'use client';

import { useEffect, useId, useRef, useState } from 'react';
import type { FormEvent, KeyboardEvent } from 'react';
import { AlertTriangle, MessageCircle, Send } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { useChat } from '@/features/chat/useChat';
import type { AlvoChat, TurnoChat } from '@/features/chat/useChat';
import { useModelosChat } from '@/features/chat/useModelosChat';
import { M } from '@/lib/mensagens';
import { ErroApi, mensagemDoErro } from '@/services/api/erros';
import { LIMITES } from '@/types/schemas';

/** Mensagem do chat para o erro: texto próprio do código; senão, o genérico. */
export function mensagemErroChat(erro: unknown): string {
  if (erro instanceof ErroApi) {
    const propria = M.chat.erros[erro.problema.erro.codigo];
    if (propria) return propria;
  }
  return mensagemDoErro(erro);
}

/** Nome curto do modelo para a lista: tira o prefixo do provedor. */
function rotuloModelo(modelo: string): string {
  return modelo.split('/').pop() ?? modelo;
}

function Turno({ turno }: { turno: TurnoChat }) {
  const { resposta } = turno;
  const baixaAncoragem = !resposta.recusou && !resposta.fundamentada;

  return (
    <li className="space-y-3">
      <div className="ml-auto max-w-[85%] rounded-xl bg-[var(--surface)] px-4 py-2 text-sm">
        <p className="mb-1 text-xs font-medium text-[var(--fg-muted)]">{M.chat.voce}</p>
        <p className="whitespace-pre-wrap break-words">{turno.pergunta}</p>
      </div>

      <div className="max-w-[92%] rounded-xl border px-4 py-3 text-sm">
        <div className="mb-1 flex flex-wrap items-center gap-2">
          <p className="text-xs font-medium text-[var(--fg-muted)]">{M.chat.assistente}</p>
          {resposta.recusou && <Badge variant="outline">{M.chat.semBase}</Badge>}
        </div>
        <p className="whitespace-pre-wrap break-words">{resposta.resposta}</p>

        {baixaAncoragem && (
          <p className="mt-2 flex items-start gap-2 text-xs text-[var(--warning)]">
            <AlertTriangle aria-hidden className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            {M.chat.baixaAncoragem}
          </p>
        )}

        {resposta.citacoes.length > 0 && (
          <details className="mt-3 text-xs">
            <summary className="cursor-pointer font-medium text-[var(--fg-muted)]">
              {M.chat.fontes(resposta.citacoes.length)}
            </summary>
            <ul className="mt-2 space-y-2">
              {resposta.citacoes.map((citacao) => (
                <li key={citacao.id} className="rounded-md border p-2">
                  <p className="font-medium">
                    [{citacao.id}] ·{' '}
                    {citacao.origem === 'documento' ? M.chat.origemDocumento : M.chat.origemPacote}
                  </p>
                  <p className="mt-1 whitespace-pre-wrap break-words text-[var(--fg-muted)]">
                    {citacao.excerto}
                  </p>
                </li>
              ))}
            </ul>
          </details>
        )}
      </div>
    </li>
  );
}

export interface ChatMaterialProps {
  alvo: AlvoChat;
}

function Conversa({ alvo }: ChatMaterialProps) {
  const { turnos, pendente, erro, espera, enviar, limpar } = useChat(alvo);
  const { data: modelos } = useModelosChat();
  const [texto, setTexto] = useState('');
  const [modeloEscolhido, setModeloEscolhido] = useState<string | null>(null);
  const fim = useRef<HTMLDivElement>(null);
  const campo = useRef<HTMLTextAreaElement>(null);
  const idCampo = useId();
  const idContador = useId();
  const idModelo = useId();

  const modeloAtual =
    modeloEscolhido && modelos?.modelos.includes(modeloEscolhido)
      ? modeloEscolhido
      : (modelos?.padrao ?? undefined);

  const tamanho = texto.trim().length;
  const longa = tamanho > LIMITES.chatPerguntaMax;
  const ocupado = pendente !== null;
  const podeEnviar = tamanho > 0 && !longa && !ocupado && espera === 0;

  useEffect(() => {
    fim.current?.scrollIntoView?.({ block: 'nearest' });
  }, [turnos.length, pendente]);

  // O campo fica desabilitado durante a consulta; ao terminar, devolve o foco a ele.
  useEffect(() => {
    if (!ocupado) campo.current?.focus({ preventScroll: true });
  }, [ocupado]);

  const submeter = async () => {
    if (!podeEnviar) return;
    const pergunta = texto;
    // Só limpa o campo se a pergunta foi respondida; na falha o texto fica para reenviar.
    if (await enviar(pergunta, modeloAtual)) setTexto('');
  };

  const aoSubmeter = (evento: FormEvent) => {
    evento.preventDefault();
    void submeter();
  };

  const aoTeclar = (evento: KeyboardEvent<HTMLTextAreaElement>) => {
    if (evento.key !== 'Enter' || evento.shiftKey || evento.nativeEvent.isComposing) return;
    evento.preventDefault();
    void submeter();
  };

  return (
    <section aria-labelledby={`${idCampo}-titulo`} className="space-y-4 rounded-xl border p-6">
      <header className="space-y-1">
        <h2 id={`${idCampo}-titulo`} className="flex items-center gap-2 text-lg font-semibold">
          <MessageCircle aria-hidden className="h-5 w-5" />
          {M.chat.titulo}
          <Badge variant="outline">{M.chat.experimental}</Badge>
        </h2>
        <p className="text-sm text-[var(--fg-muted)]">{M.chat.descricao}</p>
        <p className="text-xs text-[var(--fg-muted)]">{M.chat.avisoExperimental}</p>
      </header>

      <div role="log" aria-live="polite" aria-label={M.chat.historico} className="space-y-4">
        {turnos.length === 0 && !pendente ? (
          <p className="text-sm text-[var(--fg-muted)]">{M.chat.vazio}</p>
        ) : (
          <ul className="space-y-5">
            {turnos.map((turno) => (
              <Turno key={turno.id} turno={turno} />
            ))}
            {pendente && (
              <li className="space-y-3">
                <div className="ml-auto max-w-[85%] rounded-xl bg-[var(--surface)] px-4 py-2 text-sm">
                  <p className="mb-1 text-xs font-medium text-[var(--fg-muted)]">{M.chat.voce}</p>
                  <p className="whitespace-pre-wrap break-words">{pendente}</p>
                </div>
                <p role="status" className="text-sm text-[var(--fg-muted)]">
                  {M.chat.enviando}
                </p>
              </li>
            )}
          </ul>
        )}
        <div ref={fim} />
      </div>

      {Boolean(erro) && (
        <div
          role="alert"
          className="rounded-lg border border-[var(--danger)] px-4 py-3 text-sm text-[var(--danger)]"
        >
          <p>{mensagemErroChat(erro)}</p>
          {espera > 0 && <p className="mt-1">{M.chat.espera(espera)}</p>}
        </div>
      )}

      <form onSubmit={aoSubmeter} noValidate className="space-y-3">
        <label htmlFor={idCampo} className="block text-sm font-medium">
          {M.chat.campo}
        </label>
        <textarea
          id={idCampo}
          ref={campo}
          rows={3}
          value={texto}
          disabled={ocupado}
          placeholder={M.chat.placeholder}
          aria-invalid={longa}
          aria-describedby={idContador}
          onChange={(evento) => setTexto(evento.target.value)}
          onKeyDown={aoTeclar}
          className="w-full rounded-md border bg-[var(--surface)] p-3 text-sm"
        />
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p
            id={idContador}
            className={`text-xs ${longa ? 'text-[var(--danger)]' : 'text-[var(--fg-muted)]'}`}
          >
            {M.chat.contador(tamanho, LIMITES.chatPerguntaMax)} · {M.chat.dica}
          </p>

          <div className="flex flex-wrap items-center gap-2">
            {modelos && modelos.modelos.length > 1 && (
              <>
                <label className="sr-only" htmlFor={idModelo}>
                  {M.chat.modelo}
                </label>
                <select
                  id={idModelo}
                  value={modeloAtual}
                  disabled={ocupado}
                  onChange={(evento) => setModeloEscolhido(evento.target.value)}
                  className="h-9 max-w-[220px] rounded-md border bg-[var(--surface)] px-3 text-sm"
                >
                  {modelos.modelos.map((modelo) => (
                    <option key={modelo} value={modelo}>
                      {rotuloModelo(modelo)}
                    </option>
                  ))}
                </select>
                <Badge variant="outline">{M.chat.experimental}</Badge>
              </>
            )}
            {turnos.length > 0 && (
              <Button type="button" variant="outline" onClick={limpar} disabled={ocupado}>
                {M.chat.limpar}
              </Button>
            )}
            <Button type="submit" disabled={!podeEnviar}>
              <Send aria-hidden className="h-4 w-4" />
              {M.chat.enviar}
            </Button>
          </div>
        </div>
      </form>
    </section>
  );
}

/** Chat do material. A chave do alvo remonta a conversa ao trocar de material ou de aluno. */
export function ChatMaterial({ alvo }: ChatMaterialProps) {
  const chave =
    alvo.tipo === 'aluno' ? `a:${alvo.alunoId}:${alvo.materialId}` : `e:${alvo.materialId}`;
  return <Conversa key={chave} alvo={alvo} />;
}
