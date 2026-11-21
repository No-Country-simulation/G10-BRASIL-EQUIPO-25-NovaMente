"""Router de jobs — GET e DELETE /jobs/{job_id}."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.auth.guardas import exigir_empresa, exigir_empresa_com_chave
from app.models import JobResposta
from app.services import repositorio
from app.workers import job_worker

# Rotas da empresa: com o login ligado, sessão de empresa ou X-API-Key
# (app/auth/guardas.py). As escritas também exigem a chave com o login desligado.
router = APIRouter(
    prefix="/jobs", tags=["jobs"], dependencies=[Depends(exigir_empresa)]
)


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


@router.delete(
    "/{job_id}",
    response_model=JobResposta,
    dependencies=[Depends(exigir_empresa_com_chave)],
)
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
