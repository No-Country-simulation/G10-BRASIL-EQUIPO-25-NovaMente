"""Worker de background que executa o pipeline em uma thread separada.

O job é criado imediatamente (status ``queued``) antes de qualquer chamada
ao LLM. A thread progride pelas etapas e atualiza o repositório a cada
transição.
"""

from __future__ import annotations

import logging
import threading
import uuid
from datetime import datetime, timezone

from app.core.config import settings
from app.core.erros import NovaMenteError
from app.models import (
    AdaptacaoPacote,
    EtapaJob,
    ErroJob,
    JobResposta,
    NichoSetor,
    NivelDetalhe,
    FormatoSaida,
    PerfilDestinatario,
    OrigemDocumento,
)
from app.services import repositorio

logger = logging.getLogger(__name__)

# ── Controle de cancelamento ──────────────────────────────────────────────────
_cancelamentos: set[str] = set()
_cancel_lock = threading.Lock()


def solicitar_cancelamento(job_id: str) -> None:
    with _cancel_lock:
        _cancelamentos.add(job_id)


def _cancelado(job_id: str) -> bool:
    with _cancel_lock:
        return job_id in _cancelamentos


def _limpar_cancelamento(job_id: str) -> None:
    with _cancel_lock:
        _cancelamentos.discard(job_id)


# ── Helper de timestamps ──────────────────────────────────────────────────────


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Função principal ──────────────────────────────────────────────────────────


def _executar(
    job_id: str,
    documento_id: str,
    titulo: str,
    texto: str,
    origem: OrigemDocumento,
    nome_arquivo: str | None,
    tamanho_bytes: int | None,
    perfil: PerfilDestinatario,
    formato: FormatoSaida,
    nicho: NichoSetor,
    nivel: NivelDetalhe,
) -> None:
    """Corpo da thread — atualiza o job a cada etapa."""

    def _atualizar(
        status=None,
        etapa: EtapaJob | None = None,
        pct: int | None = None,
        msg: str | None = None,
        concluir_etapa: bool = False,
    ) -> None:
        job = repositorio.obter_job(job_id)
        if job is None:
            return
        concluidas = list(job.etapas_concluidas)
        if concluir_etapa and etapa and etapa not in concluidas:
            concluidas.append(etapa)
        novo = job.model_copy(
            update={
                k: v
                for k, v in {
                    "status": status or job.status,
                    "etapa_atual": etapa if etapa is not None else job.etapa_atual,
                    "etapas_concluidas": concluidas,
                    "progresso_percentual": pct if pct is not None else job.progresso_percentual,
                    "mensagem": msg,
                    "atualizado_em": _agora(),
                }.items()
                if v is not None or k in ("etapa_atual", "mensagem")
            }
        )
        repositorio.salvar_job(novo, settings.job_ttl_segundos)

    def on_progresso(etapa: EtapaJob, pct: int, msg: str = "") -> None:
        if _cancelado(job_id):
            raise InterruptedError("Cancelado pelo usuário.")
        _atualizar(status="running", etapa=etapa, pct=pct, msg=msg)

    try:
        # Sinaliza "extraindo" manualmente antes de chamar o pipeline
        _atualizar(status="running", etapa="extraindo", pct=10, msg="Extraindo texto...")

        if _cancelado(job_id):
            raise InterruptedError("Cancelado antes de iniciar.")

        from app.services.pipeline import executar_pipeline

        pacote = executar_pipeline(
            documento_id=documento_id,
            titulo=titulo,
            texto=texto,
            origem=origem,
            nome_arquivo=nome_arquivo,
            tamanho_bytes=tamanho_bytes,
            perfil=perfil,
            formato=formato,
            nicho=nicho,
            nivel=nivel,
            on_progresso=on_progresso,
        )

        # Persiste o pacote
        repositorio.salvar_pacote(pacote)

        # Atualiza o job para succeeded
        job = repositorio.obter_job(job_id)
        if job:
            concluidas = ["extraindo", "chunking", "embeddings", "gerando", "revisando", "armazenando"]
            novo = job.model_copy(
                update={
                    "status": "succeeded",
                    "etapa_atual": None,
                    "etapas_concluidas": concluidas,
                    "progresso_percentual": 100,
                    "mensagem": "Material gerado com sucesso.",
                    "atualizado_em": _agora(),
                    "adaptacao_id": pacote.adaptacao_id,
                    "resultado": pacote,
                }
            )
            repositorio.salvar_job(novo, settings.job_ttl_segundos)

    except InterruptedError:
        _limpar_cancelamento(job_id)
        job = repositorio.obter_job(job_id)
        if job:
            repositorio.salvar_job(
                job.model_copy(
                    update={
                        "status": "cancelled",
                        "etapa_atual": None,
                        "mensagem": "Geração cancelada pelo usuário.",
                        "atualizado_em": _agora(),
                    }
                ),
                settings.job_ttl_segundos,
            )

    except Exception as exc:
        _limpar_cancelamento(job_id)
        logger.exception("Erro no job %s", job_id)
        job = repositorio.obter_job(job_id)
        if job:
            request_id = str(uuid.uuid4())
            repositorio.salvar_job(
                job.model_copy(
                    update={
                        "status": "failed",
                        "etapa_atual": None,
                        "mensagem": str(exc),
                        "atualizado_em": _agora(),
                        "erro": ErroJob(
                            codigo="INTERNO",
                            mensagem=str(exc),
                            request_id=request_id,
                        ),
                    }
                ),
                settings.job_ttl_segundos,
            )


def criar_job(
    titulo: str,
    texto: str,
    origem: OrigemDocumento,
    nome_arquivo: str | None,
    tamanho_bytes: int | None,
    perfil: PerfilDestinatario,
    formato: FormatoSaida,
    nicho: NichoSetor,
    nivel: NivelDetalhe,
) -> JobResposta:
    """Cria o job (status queued) e dispara a thread. Retorna imediatamente."""
    from ulid import ULID  # type: ignore

    job_id = str(ULID())
    documento_id = f"doc_{job_id}"
    agora = _agora()

    job = JobResposta(
        job_id=job_id,
        status="queued",
        etapa_atual=None,
        etapas_concluidas=[],
        progresso_percentual=0,
        iniciado_em=agora,
        atualizado_em=agora,
    )
    repositorio.salvar_job(job, settings.job_ttl_segundos)

    t = threading.Thread(
        target=_executar,
        args=(
            job_id, documento_id, titulo, texto, origem,
            nome_arquivo, tamanho_bytes, perfil, formato, nicho, nivel,
        ),
        daemon=True,
    )
    t.start()
    return job
