"""Dados do cliente HTTP usados por limites e logs."""

from __future__ import annotations

import ipaddress

from starlette.requests import HTTPConnection
from starlette.types import Scope

from app.core.config import settings

IP_DESCONHECIDO = "desconhecido"


def _ultimo_ip_encaminhado(scope: Scope) -> str | None:
    """Última entrada do X-Forwarded-For, se for um IP válido.

    A última é a que o proxy confiável acrescentou (ou a única, quando ele
    sobrescreve o cabeçalho); as anteriores vêm do cliente e podem ser forjadas.
    """
    for nome, valor in scope.get("headers") or ():
        if nome == b"x-forwarded-for":
            ultimo = valor.decode("latin-1").split(",")[-1].strip()
            try:
                return str(ipaddress.ip_address(ultimo))
            except ValueError:
                return None
    return None


def ip_do_cliente(origem: HTTPConnection | Scope) -> str:
    """IP do cliente, para os limites por IP (login e gerações).

    Aceita a ``Request`` das rotas ou o ``scope`` ASGI dos middlewares.

    Por padrão é o IP da conexão e o ``X-Forwarded-For`` é ignorado: sem um
    proxy confiável na frente, o cabeçalho pode ser forjado e anularia os
    limites. Com ``CONFIAR_X_FORWARDED_FOR=true``, vale a última entrada do
    cabeçalho; ausente ou inválida, cai para o IP da conexão.
    """
    scope = origem.scope if isinstance(origem, HTTPConnection) else origem
    if settings.confiar_x_forwarded_for:
        encaminhado = _ultimo_ip_encaminhado(scope)
        if encaminhado is not None:
            return encaminhado
    cliente = scope.get("client")
    return cliente[0] if cliente else IP_DESCONHECIDO
