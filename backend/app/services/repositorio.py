"""Repositório de jobs em memória e pacotes duráveis em SQLite.

Jobs ficam em memória por ``JOB_TTL_SEGUNDOS`` (30 min) e são perdidos quando
o processo reinicia — ``GET /jobs/{id}`` passa a retornar 404 e a UI oferece
"Tentar novamente". Pacotes são persistidos na tabela ``materiais`` e
sobrevivem ao reinício; salvar um pacote cria ou atualiza o material
correspondente como rascunho.
"""

from __future__ import annotations

import threading
import time
from typing import TYPE_CHECKING

from sqlalchemy import select

from app.core.db import SessionLocal
from app.models import AdaptacaoPacote
from app.models.db import MaterialDB
from app.services.materiais import material_de_pacote

if TYPE_CHECKING:
    from app.models import JobResposta

_lock = threading.Lock()
_jobs: dict[str, "JobResposta"] = {}
_criado_em: dict[str, float] = {}   # job_id → timestamp UNIX


def salvar_job(job: "JobResposta", ttl_segundos: int = 1800) -> None:
    with _lock:
        _jobs[job.job_id] = job
        _criado_em[job.job_id] = time.time() + ttl_segundos


def obter_job(job_id: str) -> "JobResposta | None":
    _purgar()
    with _lock:
        return _jobs.get(job_id)


def salvar_pacote(pacote: AdaptacaoPacote) -> None:
    with SessionLocal() as session:
        material_de_pacote(session, pacote)
        session.commit()


def obter_pacote(adaptacao_id: str) -> AdaptacaoPacote | None:
    with SessionLocal() as session:
        row = session.scalar(
            select(MaterialDB).where(MaterialDB.adaptacao_id == adaptacao_id)
        )
        if row is None:
            return None
        return _pacote_do_json(row.pacote_json)


def listar_pacotes() -> list[AdaptacaoPacote]:
    with SessionLocal() as session:
        linhas = session.scalars(select(MaterialDB)).all()
        pacotes = (_pacote_do_json(row.pacote_json) for row in linhas)
        return [pacote for pacote in pacotes if pacote is not None]


def _pacote_do_json(pacote_json: str) -> AdaptacaoPacote | None:
    """Valida o JSON; linhas corrompidas são ignoradas em vez de derrubar a API."""
    try:
        return AdaptacaoPacote.model_validate_json(pacote_json)
    except ValueError:
        return None


def _purgar() -> None:
    agora = time.time()
    with _lock:
        expirados = [jid for jid, exp in _criado_em.items() if agora > exp]
        for jid in expirados:
            _jobs.pop(jid, None)
            _criado_em.pop(jid, None)
