'use client';

import { useState } from 'react';
import { Check, Loader2, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { ETAPAS, ROTULOS_ETAPA } from '@/lib/constants';
import { M } from '@/lib/mensagens';
import { cn } from '@/lib/cn';
import type { EtapaJob, JobResposta } from '@/types/novamente';

interface Props {
  job: JobResposta;
  estourou: boolean;
  aoCancelar: () => void;
  aoTentarNovamente: () => void;
  perdido?: boolean;
}

export function JobProgress({ job, estourou, aoCancelar, aoTentarNovamente, perdido }: Props) {
  // Progresso monotônico: guarda o maior valor já exibido e nunca regride.
  const [progresso, setProgresso] = useState(() => Math.round(job.progresso_percentual));
  const [ultimoProgressoRecebido, setUltimoProgressoRecebido] = useState(job.progresso_percentual);
  if (job.progresso_percentual !== ultimoProgressoRecebido) {
    setUltimoProgressoRecebido(job.progresso_percentual);
    setProgresso((anterior) => Math.max(anterior, Math.round(job.progresso_percentual)));
  }

  // Etapa concluída nunca é desmarcada: guarda o avanço máximo já visto e
  // considera concluídas todas as etapas anteriores à atual, mesmo quando o job
  // pula etapas no meio.
  const indiceAtual = job.etapa_atual ? ETAPAS.indexOf(job.etapa_atual) : -1;
  const indiceConcluidas = job.etapas_concluidas.reduce((maior, etapa) => Math.max(maior, ETAPAS.indexOf(etapa)), -1);
  const [indiceMaximo, setIndiceMaximo] = useState(() => Math.max(indiceAtual, indiceConcluidas));
  const [chaveChecklist, setChaveChecklist] = useState(() => `${indiceAtual}|${indiceConcluidas}`);
  const chaveAtual = `${indiceAtual}|${indiceConcluidas}`;
  if (chaveAtual !== chaveChecklist) {
    setChaveChecklist(chaveAtual);
    setIndiceMaximo((anterior) => Math.max(anterior, indiceAtual, indiceConcluidas));
  }
  // `slice(0, -1)` marcaria cinco etapas falsas em job na fila; o limite nunca é negativo.
  const limite = Math.max(0, indiceMaximo, indiceConcluidas);
  const concluidas = new Set<EtapaJob>([...ETAPAS.slice(0, limite), ...job.etapas_concluidas]);

  const falhou = estourou || Boolean(perdido) || job.status === 'failed';
  const mensagem = estourou ? M.job.timeout : perdido ? M.job.perdida : job.erro?.mensagem;

  return (
    <section aria-labelledby="job-titulo" className="rounded-xl border p-6">
      <h2 id="job-titulo" className="text-lg font-semibold">
        {falhou ? M.job.falhaTitulo : M.job.titulo}
      </h2>

      <Progress
        value={progresso}
        aria-label={M.job.progresso}
        aria-valuetext={
          job.etapa_atual
            ? M.job.progressoValorTexto(progresso, ROTULOS_ETAPA[job.etapa_atual])
            : `${progresso}%`
        }
        className="mt-4"
      />
      <p className="mt-2 text-sm text-[var(--fg-muted)]">{progresso}%</p>

      <ol className="mt-6 space-y-3">
        {ETAPAS.map((etapa) => {
          const concluida = concluidas.has(etapa);
          const atual = job.etapa_atual === etapa && !falhou;
          return (
            <li
              key={etapa}
              aria-current={atual ? 'step' : undefined}
              className={cn('flex items-center gap-3 text-sm', !concluida && !atual && 'text-[var(--fg-muted)]')}
            >
              {concluida ? (
                <Check aria-hidden className="h-4 w-4 text-[var(--success)]" />
              ) : atual ? (
                <Loader2 aria-hidden className="h-4 w-4 animate-spin text-[var(--accent)]" />
              ) : (
                <span aria-hidden className="h-4 w-4 rounded-full border" />
              )}
              <span>{ROTULOS_ETAPA[etapa]}</span>
            </li>
          );
        })}
      </ol>

      {/* Região viva: só a etapa muda de forma anunciável; mensagens livres do
          backend são renderizadas fora dela para não falar a cada poll. */}
      <div aria-live="polite" className="mt-4 min-h-6 text-sm">
        {falhou ? (
          <div className="text-[var(--danger)]">
            <p className="flex items-center gap-2">
              <X aria-hidden className="h-4 w-4" />
              {mensagem}
            </p>
            {job.erro?.request_id && (
              <p className="mt-1 font-mono text-xs text-[var(--fg-muted)]">{M.job.requestId(job.erro.request_id)}</p>
            )}
          </div>
        ) : (
          job.etapa_atual && (
            <p key={job.etapa_atual}>{M.job.etapaAtual(ROTULOS_ETAPA[job.etapa_atual])}</p>
          )
        )}
      </div>
      {!falhou && job.mensagem && (
        <p className="mt-1 text-sm text-[var(--fg-muted)]">{job.mensagem}</p>
      )}

      <div className="mt-6 flex gap-3">
        {falhou ? (
          <Button onClick={aoTentarNovamente}>{M.comum.tentarNovamente}</Button>
        ) : (
          <Button variant="outline" onClick={aoCancelar}>
            {M.formulario.cancelarGeracao}
          </Button>
        )}
      </div>
    </section>
  );
}
