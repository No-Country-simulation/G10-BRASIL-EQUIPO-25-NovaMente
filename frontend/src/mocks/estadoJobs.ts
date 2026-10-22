import type { AdaptacaoPacote, AdaptacaoResumo, EtapaJob, JobResposta } from '@/types/novamente';
import { ETAPAS, LIMITE_TEMPO_JOB_MS } from '@/lib/constants';
import flashcards from './fixtures/flashcards-vcn-iniciante.json';
import quiz from './fixtures/quiz-vcn-desenvolvedor.json';
import tutorial from './fixtures/tutorial-vcn-lider.json';
import resumo from './fixtures/resumo-vcn-gestor.json';

interface Registro {
  job: JobResposta;
  pacote: AdaptacaoPacote;
  inicio: number;
  duracao: number;
}

const jobs = new Map<string, Registro>();
const pacotes = new Map<string, AdaptacaoPacote>();
let duracaoPadrao = 6000;
let sequencia = 0;

// Faixas progressivas de progresso, uma por etapa, terminando em 100.
const FAIXAS = [20, 35, 55, 80, 90, 100];

export function configurarDuracaoJob(ms: number) {
  duracaoPadrao = ms;
}

function agoraIso() {
  return new Date().toISOString();
}

export function novoId(): string {
  sequencia += 1;
  return `01JMOCK${String(sequencia).padStart(18, '0')}`;
}

export function criarJob(pacote: AdaptacaoPacote, duracao = duracaoPadrao): JobResposta {
  const job: JobResposta = {
    job_id: novoId(),
    status: 'queued',
    etapa_atual: null,
    etapas_concluidas: [],
    progresso_percentual: 0,
    iniciado_em: agoraIso(),
    atualizado_em: agoraIso(),
  };
  jobs.set(job.job_id, { job, pacote, inicio: Date.now(), duracao: Math.max(1, duracao) });
  return structuredClone(job);
}

function avancar(registro: Registro): JobResposta {
  if (
    registro.job.status === 'succeeded' ||
    registro.job.status === 'failed' ||
    registro.job.status === 'cancelled'
  ) {
    return structuredClone(registro.job);
  }

  // Mesmo limite de tempo do cliente: nenhum job fica "rodando" para sempre.
  if (Date.now() - registro.inicio > LIMITE_TEMPO_JOB_MS) {
    registro.job = {
      ...registro.job,
      status: 'failed',
      etapa_atual: null,
      mensagem: undefined,
      atualizado_em: agoraIso(),
      erro: { codigo: 'INTERNO', mensagem: 'A geração excedeu o tempo limite de 5 minutos.' },
    };
    return structuredClone(registro.job);
  }

  const razao = Math.min(1, (Date.now() - registro.inicio) / registro.duracao);
  const indice = Math.min(ETAPAS.length - 1, Math.floor(razao * ETAPAS.length));
  const progresso = razao >= 1 ? 100 : FAIXAS[indice];
  const concluido = razao >= 1;

  registro.job = {
    ...registro.job,
    status: concluido ? 'succeeded' : 'running',
    etapa_atual: concluido ? null : (ETAPAS[indice] as EtapaJob),
    etapas_concluidas: concluido ? [...ETAPAS] : ETAPAS.slice(0, indice),
    progresso_percentual: progresso,
    mensagem: concluido ? undefined : `Etapa: ${ETAPAS[indice]}`,
    atualizado_em: agoraIso(),
    ...(concluido ? { adaptacao_id: registro.pacote.adaptacao_id, resultado: registro.pacote } : {}),
  };

  if (concluido) pacotes.set(registro.pacote.adaptacao_id, registro.pacote);
  return structuredClone(registro.job);
}

export function obterJob(jobId: string): JobResposta | undefined {
  const registro = jobs.get(jobId);
  if (!registro) return undefined;
  return avancar(registro);
}

export function cancelarJob(jobId: string): JobResposta | 'finalizado' | undefined {
  const registro = jobs.get(jobId);
  if (!registro) return undefined;
  if (['succeeded', 'failed', 'cancelled'].includes(registro.job.status)) return 'finalizado';
  registro.job = { ...registro.job, status: 'cancelled', etapa_atual: null, atualizado_em: agoraIso() };
  return structuredClone(registro.job);
}

export function registrarPacote(pacote: AdaptacaoPacote) {
  pacotes.set(pacote.adaptacao_id, pacote);
}

export function obterPacote(id: string): AdaptacaoPacote | undefined {
  return pacotes.get(id);
}

export function listarPacotes(): AdaptacaoPacote[] {
  return [...pacotes.values()].sort((a, b) => Date.parse(b.criado_em) - Date.parse(a.criado_em));
}

export function resumir(pacote: AdaptacaoPacote): AdaptacaoResumo {
  return {
    adaptacao_id: pacote.adaptacao_id,
    criado_em: pacote.criado_em,
    documento: pacote.documento,
    perfil_aplicado: pacote.metadados.perfil_aplicado,
    formato_gerado: pacote.metadados.formato_gerado,
    nivel_detalhe_aplicado: pacote.metadados.nivel_detalhe_aplicado,
    tempo_estimado_estudo_minutos: pacote.metadados.tempo_estimado_estudo_minutos,
    ancoragem_fonte_score: pacote.avaliacao_qualidade.ancoragem_fonte_score,
    status_upload: pacote.armazenamento_oci.status_upload,
    conceitos_chave: pacote.metadados.conceitos_chave.slice(0, 6),
  };
}

export function semearHistorico(quantidade: number) {
  const bases = [flashcards, quiz, tutorial, resumo] as unknown as AdaptacaoPacote[];
  for (let i = 0; i < quantidade; i += 1) {
    const base = structuredClone(bases[i % bases.length]);
    base.adaptacao_id = `01JSEED${String(i).padStart(19, '0')}`;
    base.criado_em = new Date(Date.now() - (i + 1) * 3_600_000).toISOString();
    base.documento = { ...base.documento, titulo: `Manual de exemplo ${i + 1}` };
    pacotes.set(base.adaptacao_id, base);
  }
}

export function limparEstadoMock() {
  jobs.clear();
  pacotes.clear();
  sequencia = 0;
  duracaoPadrao = 6000;
}
