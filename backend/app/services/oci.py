"""Serviço de integração com OCI Object Storage.

Se as variáveis de ambiente de OCI não estiverem configuradas, o módulo
entra em modo degradado: ``configurado = False`` e o upload retorna
``status_upload = "falha"`` sem lançar exceção (comportamento especificado
na seção 6.10 da spec do frontend).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from app.core.config import settings
from app.models import AdaptacaoPacote, ArmazenamentoOci, OciStatus

logger = logging.getLogger(__name__)


def _cliente_oci():
    """Retorna (object_storage_client, namespace) ou (None, None)."""
    if not settings.oci_namespace:
        return None, None
    try:
        import oci  # type: ignore

        config = oci.config.from_file(
            settings.oci_config_file, settings.oci_profile
        )
        client = oci.object_storage.ObjectStorageClient(config)
        return client, settings.oci_namespace
    except Exception as exc:
        logger.warning("OCI indisponível: %s", exc)
        return None, None


def fazer_upload(pacote: AdaptacaoPacote, objeto_id: str) -> ArmazenamentoOci:
    """Salva o pacote no bucket OCI.

    Retorna ``ArmazenamentoOci`` com ``status_upload = 'falha'`` se OCI não
    estiver configurado ou se a chamada falhar; nunca lança exceção para o
    caller.
    """
    client, namespace = _cliente_oci()
    if client is None:
        logger.warning("OCI não configurado; upload ignorado.")
        return ArmazenamentoOci(
            bucket=settings.oci_bucket,
            objeto_id=objeto_id,
            status_upload="falha",
        )

    payload = pacote.model_dump_json(indent=2).encode()
    try:
        client.put_object(
            namespace_name=namespace,
            bucket_name=settings.oci_bucket,
            object_name=objeto_id,
            put_object_body=payload,
            content_type="application/json; charset=utf-8",
        )
        return ArmazenamentoOci(
            bucket=settings.oci_bucket,
            objeto_id=objeto_id,
            status_upload="concluido",
        )
    except Exception as exc:
        logger.error("Falha no upload OCI: %s", exc)
        return ArmazenamentoOci(
            bucket=settings.oci_bucket,
            objeto_id=objeto_id,
            status_upload="falha",
        )


def obter_status() -> OciStatus:
    """Consulta o bucket e devolve um ``OciStatus``.

    Nunca lança exceção: retorna ``configurado=False`` ou
    ``configurado=True`` com contadores quando o OCI responde.
    """
    agora = datetime.now(timezone.utc).isoformat()
    client, namespace = _cliente_oci()

    if client is None:
        return OciStatus(
            configurado=False,
            mensagem="Credenciais OCI não configuradas.",
            verificado_em=agora,
        )

    try:
        resp = client.list_objects(
            namespace_name=namespace,
            bucket_name=settings.oci_bucket,
            fields="size",
        )
        objetos = resp.data.objects or []
        total = len(objetos)
        bytes_total = sum(o.size or 0 for o in objetos)
        ultimo = max((o.time_modified for o in objetos), default=None)
        return OciStatus(
            configurado=True,
            bucket=settings.oci_bucket,
            regiao=settings.oci_regiao or None,
            total_objetos=total,
            bytes_armazenados=bytes_total,
            ultimo_upload_em=ultimo.isoformat() if ultimo else None,
            verificado_em=agora,
        )
    except Exception as exc:
        logger.error("Erro ao consultar OCI: %s", exc)
        return OciStatus(
            configurado=True,
            mensagem=str(exc),
            verificado_em=agora,
        )
