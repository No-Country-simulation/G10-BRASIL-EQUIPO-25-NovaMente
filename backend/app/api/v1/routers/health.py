"""Router de health check — GET /health."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter

from app.core.config import settings
from app.models import HealthResposta

router = APIRouter(tags=["infra"])


@router.get("/health", response_model=HealthResposta)
def health() -> HealthResposta:
    """Liveness check + estado das dependências externas."""
    agora = datetime.now(timezone.utc).isoformat()

    # OCI
    try:
        from app.services.oci import obter_status
        oci_status = obter_status()
        oci_ok = "ok" if oci_status.configurado else "indisponivel"
    except Exception:
        oci_ok = "indisponivel"

    # LLM — verifica apenas se a chave está configurada
    llm_ok = "ok" if settings.google_api_key else "indisponivel"

    status_geral = "ok" if oci_ok == "ok" and llm_ok == "ok" else "degraded"

    return HealthResposta(
        status=status_geral,
        versao=settings.app_versao,
        oci=oci_ok,
        llm=llm_ok,
        verificado_em=agora,
    )
