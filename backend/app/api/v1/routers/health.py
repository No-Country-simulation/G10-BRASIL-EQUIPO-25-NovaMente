"""Router de health check — GET /health."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import datetime, timezone

from fastapi import APIRouter

from app.core.config import settings
from app.core.preparo_banco import caminhos_do_banco
from app.models import HealthResposta

router = APIRouter(tags=["infra"])

_TIMEOUT_BANCO_SEGUNDOS = 1  # o health não pode ficar preso num banco travado


def _estado_banco() -> str:
    """``ok`` se todos os arquivos SQLite configurados abrem e respondem a uma consulta.

    O arquivo é aberto em modo leitura e escrita sem criá-lo: se o volume sumiu ou o
    arquivo foi apagado, o estado é ``indisponivel``. Nem o caminho nem a mensagem
    do erro saem na resposta.
    """
    try:
        for _variavel, caminho in caminhos_do_banco(settings.db_path, settings.database_url):
            uri = f"{caminho.resolve().as_uri()}?mode=rw"
            with closing(sqlite3.connect(uri, uri=True, timeout=_TIMEOUT_BANCO_SEGUNDOS)) as conexao:
                conexao.execute("SELECT 1 FROM sqlite_master LIMIT 1").fetchall()
    except Exception:
        return "indisponivel"
    return "ok"


@router.get("/health", response_model=HealthResposta)
def health() -> HealthResposta:
    """Liveness check + estado das dependências.

    Responde 200 mesmo com dependência indisponível; o problema aparece em
    ``status: degraded`` e no campo da dependência.
    """
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

    # Banco — SQLite acessível (arquivo de jobs/histórico e do catálogo)
    banco_ok = _estado_banco()

    status_geral = "ok" if oci_ok == "ok" and llm_ok == "ok" and banco_ok == "ok" else "degraded"

    return HealthResposta(
        status=status_geral,
        versao=settings.app_versao,
        oci=oci_ok,
        llm=llm_ok,
        banco=banco_ok,
        verificado_em=agora,
    )
