"""Router de jobs — GET e DELETE /jobs/{job_id}."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.models import JobResposta
from app.services import repositorio
from app.workers import job_worker

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}", response_model=JobResposta)
def obter_job(job_id: str) -> JobResposta:
    """Retorna o estado atual do job para polling pelo frontend."""
    job = repositorio.obter_job(job_id)
    if job is None:
        raise HTTPException(
            status_code=404,
            detail={
                "erro": {
                    "codigo": "JOB_NAO_ENCONTRADO",
                    "mensagem": "Job não encontrado ou expirado. Tente novamente.",
                }
            },
        )
    return job


@router.delete("/{job_id}", response_model=JobResposta)
def cancelar_job(job_id: str) -> JobResposta:
    """Cancela um job em andamento."""
    job = repositorio.obter_job(job_id)
    if job is None:
        raise HTTPException(
            status_code=404,
            detail={
                "erro": {
                    "codigo": "JOB_NAO_ENCONTRADO",
                    "mensagem": "Job não encontrado ou expirado.",
                }
            },
        )
    if job.status in ("succeeded", "failed", "cancelled"):
        raise HTTPException(
            status_code=409,
            detail={
                "erro": {
                    "codigo": "JOB_FINALIZADO",
                    "mensagem": f"Não é possível cancelar um job com status '{job.status}'.",
                }
            },
        )
    job_worker.solicitar_cancelamento(job_id)
    # Devolve o estado atual; a thread atualizará para 'cancelled' em breve
    return job
