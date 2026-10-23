'use client';

import { useId } from 'react';
import { AlertTriangle, Database } from 'lucide-react';
import { ScoreGauge } from './ScoreGauge';
import { M } from '@/lib/mensagens';
import { formatarDataRelativa } from '@/lib/formatadores';
import type { AdaptacaoPacote, OciStatus } from '@/types/novamente';

interface Props {
  armazenamento: AdaptacaoPacote['armazenamento_oci'];
  avaliacao: AdaptacaoPacote['avaliacao_qualidade'];
  oci?: OciStatus;
}

export function OCIPanel({ armazenamento, avaliacao, oci }: Props) {
  const tituloId = useId();

  return (
    <aside aria-labelledby={tituloId} className="space-y-5 rounded-xl border p-5">
      <h2 id={tituloId} className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wide">
        <Database aria-hidden className="h-4 w-4 text-[var(--accent)]" />
        {M.oci.titulo}
      </h2>

      <ScoreGauge valor={avaliacao.ancoragem_fonte_score} rotulo={M.resultado.ancoragem} />

      <div>
        <p className="text-sm text-[var(--fg-muted)]">{M.resultado.clareza}</p>
        <p className="text-base font-medium">{avaliacao.clareza_pedagogica}</p>
      </div>

      {avaliacao.observacoes && (
        <div>
          <p className="text-sm text-[var(--fg-muted)]">{M.resultado.observacoes}</p>
          <p className="text-sm">{avaliacao.observacoes}</p>
        </div>
      )}

      <dl className="space-y-2 border-t pt-4 text-sm">
        <div>
          <dt className="text-[var(--fg-muted)]">{M.resultado.bucket}</dt>
          <dd className="font-mono text-xs">{armazenamento.bucket}</dd>
        </div>
        <div>
          <dt className="text-[var(--fg-muted)]">{M.resultado.objeto}</dt>
          <dd className="truncate font-mono text-xs" title={armazenamento.objeto_id}>
            {armazenamento.objeto_id}
          </dd>
        </div>
        <div>
          <dt className="text-[var(--fg-muted)]">{M.oci.status}</dt>
          <dd>
            {armazenamento.status_upload === 'concluido' ? (
              <span className="text-[var(--success)]">{M.oci.concluido}</span>
            ) : (
              <span className="flex items-center gap-1 text-[var(--warning)]">
                <AlertTriangle aria-hidden className="h-4 w-4" />
                {M.oci.falhaUpload}
              </span>
            )}
          </dd>
        </div>
      </dl>

      {armazenamento.status_upload === 'falha' && (
        <p role="alert" className="rounded-md border border-[var(--warning)] p-3 text-sm text-[var(--warning)]">
          {M.resultado.naoPersistido}
        </p>
      )}

      {oci && !oci.configurado && (
        <p className="rounded-md border p-3 text-sm text-[var(--fg-muted)]">
          <span className="font-medium text-[var(--fg)]">{M.oci.naoConfigurado}</span>
          {oci.mensagem && <span> — {oci.mensagem}</span>}
        </p>
      )}

      {oci?.configurado && (oci.total_objetos !== undefined || oci.ultimo_upload_em) && (
        <dl className="space-y-1 border-t pt-4 text-xs text-[var(--fg-muted)]">
          {oci.total_objetos !== undefined && (
            <div className="flex justify-between">
              <dt>{M.oci.objetos}</dt>
              <dd>{oci.total_objetos}</dd>
            </div>
          )}
          {oci.ultimo_upload_em && (
            <div className="flex justify-between gap-2">
              <dt>{M.oci.ultimoUpload}</dt>
              <dd>{formatarDataRelativa(oci.ultimo_upload_em)}</dd>
            </div>
          )}
        </dl>
      )}
    </aside>
  );
}
