"""Router de OCI — GET /oci/status."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.auth.guardas import exigir_empresa
from app.models import OciStatus
from app.services import oci as oci_service

# Rotas da empresa: com o login ligado, exigem sessão de empresa.
router = APIRouter(
    prefix="/oci", tags=["oci"], dependencies=[Depends(exigir_empresa)]
)


@router.get("/status", response_model=OciStatus)
def status_oci() -> OciStatus:
    """Retorna o status do bucket OCI (com cache de 30 s implícito no cliente)."""
    return oci_service.obter_status()
