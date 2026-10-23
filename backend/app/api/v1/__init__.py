"""Agrega todos os routers da API v1."""

from fastapi import APIRouter

from app.api.v1.routers import adaptacoes, health, jobs, oci

router = APIRouter(prefix="/api/v1")
router.include_router(adaptacoes.router)
router.include_router(jobs.router)
router.include_router(oci.router)
# health é incluído diretamente (sem sub-prefixo)
router.include_router(health.router)

__all__ = ["router"]
