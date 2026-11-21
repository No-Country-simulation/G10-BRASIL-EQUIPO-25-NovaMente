"""Limite de requisições por IP nos endpoints que disparam o LLM.

Middleware ASGI que conta os POST em ``/api/v1/adaptacoes`` e
``/api/v1/adaptacoes/upload`` por IP de cliente, com ``LimiteDeTaxa``
(janela deslizante de um minuto, em memória). Acima de
``geracao_limite_por_minuto`` responde 429 com ``Retry-After``.

Só a requisição que cria um job (202) consome o limite: a vaga é reservada
antes da rota, para que requisições simultâneas não passem juntas, e devolvida
se a resposta não for 202 (validação, 413, 415, 503...). O que custa LLM é a
geração; erro de preenchimento não deve esgotar o limite de quem está usando
o sistema. O contador é por processo, como o ``LimiteDeTaxa``.
"""

from __future__ import annotations

import ipaddress

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import settings
from app.core.limite_taxa import LimiteDeTaxa, segundos_para_cabecalho

ROTAS_GERACAO = frozenset({"/api/v1/adaptacoes", "/api/v1/adaptacoes/upload"})


class LimitePorIp(LimiteDeTaxa):
    """``LimiteDeTaxa`` que também permite devolver a última vaga reservada."""

    def devolver(self, chave: str) -> None:
        with self._trava:
            instantes = self._chaves.get(chave)
            if instantes:
                instantes.pop()


# Lido a cada requisição: acompanha mudanças em settings (e os testes).
limitador = LimitePorIp(lambda: settings.geracao_limite_por_minuto)


def ip_do_cliente(scope: Scope) -> str:
    """IP usado como chave do limite.

    Por padrão, o IP da conexão. Com ``CONFIAR_X_FORWARDED_FOR`` ligada, usa a
    última entrada do ``X-Forwarded-For``, a que o proxy confiável acrescentou
    (as anteriores vêm do cliente e podem ser forjadas). Valor que não é um IP
    é ignorado.
    """
    if settings.confiar_x_forwarded_for:
        for nome, valor in scope["headers"]:
            if nome == b"x-forwarded-for":
                ultimo = valor.decode("latin-1").split(",")[-1].strip()
                try:
                    return str(ipaddress.ip_address(ultimo))
                except ValueError:
                    break
    cliente = scope.get("client")
    return cliente[0] if cliente else "desconhecido"


class LimiteGeracaoMiddleware:
    """Responde 429 quando o IP passa do limite de gerações por minuto."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            scope["type"] != "http"
            or scope["method"] != "POST"
            or scope["path"].rstrip("/") not in ROTAS_GERACAO
        ):
            await self.app(scope, receive, send)
            return

        chave = ip_do_cliente(scope)
        espera = limitador.registrar(chave)
        if espera is not None:
            segundos = segundos_para_cabecalho(espera)
            resposta = JSONResponse(
                {
                    "erro": {
                        "codigo": "LIMITE_EXCEDIDO",
                        "mensagem": (
                            "Muitas gerações em pouco tempo. "
                            f"Tente novamente em {segundos} segundos."
                        ),
                    }
                },
                status_code=429,
                headers={"Retry-After": str(segundos)},
            )
            await resposta(scope, receive, send)
            return

        criou_job = False

        async def enviar(mensagem: Message) -> None:
            nonlocal criou_job
            if mensagem["type"] == "http.response.start":
                criou_job = mensagem["status"] == 202
            await send(mensagem)

        try:
            await self.app(scope, receive, enviar)
        finally:
            if not criou_job:
                limitador.devolver(chave)
