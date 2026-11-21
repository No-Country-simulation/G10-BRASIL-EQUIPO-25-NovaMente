"""Dados do cliente HTTP usados por limites e logs."""

from __future__ import annotations

import ipaddress

from fastapi import Request

from app.core.config import settings

IP_DESCONHECIDO = "desconhecido"


def _primeiro_ip_encaminhado(cabecalho: str | None) -> str | None:
    """Primeiro valor (o mais à esquerda) do X-Forwarded-For, se for um IP válido."""
    if not cabecalho:
        return None
    primeiro = cabecalho.split(",")[0].strip()
    try:
        return str(ipaddress.ip_address(primeiro))
    except ValueError:
        return None


def ip_do_cliente(request: Request) -> str:
    """IP do cliente, para os limites por IP.

    Por padrão é o IP da conexão (``request.client.host``) e o
    ``X-Forwarded-For`` é ignorado: sem um proxy confiável na frente, o
    cabeçalho pode ser forjado e anularia os limites. Com
    ``CONFIAR_X_FORWARDED_FOR=true`` (Caddy como primeiro salto, substituindo o
    cabeçalho do cliente), vale o primeiro IP da lista; cabeçalho ausente ou
    inválido cai para o IP da conexão.
    """
    if settings.confiar_x_forwarded_for:
        encaminhado = _primeiro_ip_encaminhado(request.headers.get("x-forwarded-for"))
        if encaminhado is not None:
            return encaminhado
    return request.client.host if request.client else IP_DESCONHECIDO
