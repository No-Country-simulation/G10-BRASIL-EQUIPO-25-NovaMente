"""Worker de background que executa o pipeline em uma thread separada.

O job é criado imediatamente (status ``queued``) antes de qualquer chamada
ao LLM. A thread progride pelas etapas e atualiza o repositório a cada
transição.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from datetime import datetime, timezone

from pydantic import ValidationError

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


class PrazoExcedido(Exception):
    """O job ultrapassou ``settings.job_timeout_segundos``."""


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
    ) -> None:
        job = repositorio.obter_job(job_id)
        if job is None:
            return
        concluidas = list(job.etapas_concluidas)
        # Ao entrar numa etapa nova, a anterior passa a constar como concluída.
        anterior = job.etapa_atual
        if etapa and anterior and etapa != anterior and anterior not in concluidas:
            concluidas.append(anterior)
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

    # Instante monotônico em que o job expira; também limita as retentativas do LLM.
    prazo = time.monotonic() + settings.job_timeout_segundos

    def verificar_cancelamento() -> None:
        if _cancelado(job_id):
            raise InterruptedError("Cancelado pelo usuário.")

    def on_progresso(etapa: EtapaJob, pct: int, msg: str = "") -> None:
        verificar_cancelamento()
        if time.monotonic() > prazo:
            raise PrazoExcedido("Prazo total do job excedido.")
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
            prazo=prazo,
            verificar_interrupcao=verificar_cancelamento,
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

    except PrazoExcedido:
        _limpar_cancelamento(job_id)
        logger.warning("Job %s excedeu o prazo de %ss", job_id, settings.job_timeout_segundos)
        minutos = f"{settings.job_timeout_segundos / 60:g}".replace(".", ",")
        _marcar_falha(job_id, f"A geração excedeu o tempo limite de {minutos} minutos.")

    except Exception as exc:
        _limpar_cancelamento(job_id)
        request_id = str(uuid.uuid4())
        logger.exception("Erro no job %s (request_id=%s)", job_id, request_id)
        # ValueError/RuntimeError trazem mensagens nossas, já em português;
        # ValidationError (subclasse de ValueError) traz texto técnico do pydantic.
        if isinstance(exc, (ValueError, RuntimeError)) and not isinstance(exc, ValidationError):
            mensagem = str(exc)
        else:
            mensagem = "Erro interno ao gerar o material."
        _marcar_falha(job_id, mensagem, request_id)


def _marcar_falha(job_id: str, mensagem: str, request_id: str | None = None) -> None:
    """Marca o job como ``failed`` com código INTERNO."""
    job = repositorio.obter_job(job_id)
    if job is None:
        return
    repositorio.salvar_job(
        job.model_copy(
            update={
                "status": "failed",
                "etapa_atual": None,
                "mensagem": mensagem,
                "atualizado_em": _agora(),
                "erro": ErroJob(
                    codigo="INTERNO",
                    mensagem=mensagem,
                    request_id=request_id or str(uuid.uuid4()),
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
