"""Credencial simples para as rotas da área da empresa (cabeçalho X-API-Key)."""

from __future__ import annotations

import hmac
import logging
import threading
from typing import Annotated

from fastapi import Depends, HTTPException
from fastapi.security import APIKeyHeader

from app.core.config import settings

logger = logging.getLogger(__name__)

NOME_CABECALHO = "X-API-Key"

_cabecalho_chave = APIKeyHeader(name=NOME_CABECALHO, auto_error=False)
# Mesmo extrator, usado pelo exigir_empresa (app/auth/guardas.py) com o login ligado.
cabecalho_chave_empresa = _cabecalho_chave

_trava_aviso = threading.Lock()
_aviso_emitido = False


def _nao_autorizado() -> HTTPException:
    # Mesma resposta para chave ausente e chave errada: não revela nada sobre a chave.
    return HTTPException(
        status_code=401,
        detail={
            "erro": {
                "codigo": "NAO_AUTORIZADO",
                "mensagem": (
                    "Acesso não autorizado. "
                    f"Informe uma chave de API válida no cabeçalho {NOME_CABECALHO}."
                ),
            }
        },
    )


def _chave_configurada() -> str:
    """Chave da empresa lida em tempo de requisição; vazio ou só espaços = não configurada."""
    return (settings.api_key_empresa or "").strip()


def _avisar_uma_vez() -> None:
    """Registra o aviso de rotas abertas na primeira requisição protegida do processo."""
    global _aviso_emitido
    if _aviso_emitido:
        return
    with _trava_aviso:
        if _aviso_emitido:
            return
        _aviso_emitido = True
    logger.warning(
        "API_KEY_EMPRESA não configurada: as rotas da empresa estão abertas. "
        "Defina a variável antes de expor o backend publicamente."
    )


def _reiniciar_aviso() -> None:
    """Rearma o aviso único (uso em testes)."""
    global _aviso_emitido
    with _trava_aviso:
        _aviso_emitido = False


def chave_empresa_confere(chave_enviada: str | None) -> bool:
    """True se há chave configurada e a enviada é igual a ela (tempo constante)."""
    esperada = _chave_configurada()
    if not esperada or not chave_enviada:
        return False
    return hmac.compare_digest(chave_enviada.encode("utf-8"), esperada.encode("utf-8"))


def exigir_chave_empresa(
    chave_enviada: Annotated[str | None, Depends(_cabecalho_chave)] = None,
) -> None:
    """Regra da chave com o login desligado (usada por ``exigir_empresa_com_chave``).

    Sem API_KEY_EMPRESA, mantém o comportamento aberto (dev local e testes) e
    avisa no log uma única vez. Com a variável, exige X-API-Key igual a ela,
    comparando em tempo constante.

    Com o login ligado não faz nada: quem decide é ``exigir_empresa``
    (app/auth/guardas.py), que aceita a sessão de empresa ou esta mesma chave.
    """
    if settings.auth_habilitada:
        return
    if not _chave_configurada():
        _avisar_uma_vez()
        return
    if not chave_empresa_confere(chave_enviada):
        raise _nao_autorizado()
