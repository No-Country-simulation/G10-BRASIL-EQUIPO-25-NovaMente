"""Router de OCI — GET /oci/status."""

from __future__ import annotations

from fastapi import APIRouter

from app.models import OciStatus
from app.services import oci as oci_service

router = APIRouter(prefix="/oci", tags=["oci"])


@router.get("/status", response_model=OciStatus)
def status_oci() -> OciStatus:
    """Retorna o status do bucket OCI (com cache de 30 s implícito no cliente)."""
    return oci_service.obter_status()
