"""Repositório em memória de jobs e pacotes de adaptação.

Não há banco de dados externo: jobs ficam em memória por ``JOB_TTL_SEGUNDOS``
(30 min) e pacotes ficam até o processo morrer. Após reinício,
``GET /jobs/{id}`` retorna 404 e a UI oferece "Tentar novamente".
"""

from __future__ import annotations

import threading
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models import AdaptacaoPacote, JobResposta

_lock = threading.Lock()
_jobs: dict[str, "JobResposta"] = {}
_pacotes: dict[str, "AdaptacaoPacote"] = {}
_criado_em: dict[str, float] = {}   # job_id → timestamp UNIX


def salvar_job(job: "JobResposta", ttl_segundos: int = 1800) -> None:
    with _lock:
        _jobs[job.job_id] = job
        _criado_em[job.job_id] = time.time() + ttl_segundos


def obter_job(job_id: str) -> "JobResposta | None":
    _purgar()
    with _lock:
        return _jobs.get(job_id)


def salvar_pacote(pacote: "AdaptacaoPacote") -> None:
    with _lock:
        _pacotes[pacote.adaptacao_id] = pacote


def obter_pacote(adaptacao_id: str) -> "AdaptacaoPacote | None":
    with _lock:
        return _pacotes.get(adaptacao_id)


def listar_pacotes() -> list["AdaptacaoPacote"]:
    with _lock:
        return list(_pacotes.values())


def _purgar() -> None:
    agora = time.time()
    with _lock:
        expirados = [jid for jid, exp in _criado_em.items() if agora > exp]
        for jid in expirados:
            _jobs.pop(jid, None)
            _criado_em.pop(jid, None)
