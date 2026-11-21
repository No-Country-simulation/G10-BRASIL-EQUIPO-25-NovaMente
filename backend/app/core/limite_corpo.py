"""Limite de tamanho do corpo do upload, aplicado antes de o arquivo ser lido.

O Starlette recebe o corpo multipart inteiro (e o grava em arquivo temporário)
antes de chamar a rota. Por isso a checagem dentro da rota, depois do
``read()``, já chegou tarde. Este middleware ASGI recusa o envio cedo:

- com ``Content-Length`` acima do limite, responde 413 sem ler o corpo;
- sem ele (envio em blocos), conta os bytes recebidos e interrompe a leitura
  ao passar do limite.

O limite do corpo é ``arquivo_max_bytes`` mais uma folga fixa para o
overhead do multipart (cabeçalhos das partes e campos do formulário).
"""

from __future__ import annotations

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import settings

ROTA_UPLOAD = "/api/v1/adaptacoes/upload"
FOLGA_MULTIPART_BYTES = 64 * 1024  # campos do formulário e delimitadores do multipart
TAMANHO_BLOCO = 64 * 1024  # leitura do arquivo em blocos


class ArquivoGrandeDemais(Exception):
    """O arquivo ultrapassou ``arquivo_max_bytes``."""


def mensagem_limite_arquivo() -> str:
    """Texto do 413, com o limite configurado (10 MiB por padrão)."""
    mib = settings.arquivo_max_bytes / (1024 * 1024)
    return f"Arquivo excede o limite de {mib:g} MiB."


def corpo_413() -> dict:
    """Envelope de erro do 413, o mesmo usado pela rota de upload."""
    return {"erro": {"codigo": "LIMITE_EXCEDIDO", "mensagem": mensagem_limite_arquivo()}}


def limite_do_corpo() -> int:
    return settings.arquivo_max_bytes + FOLGA_MULTIPART_BYTES


async def ler_arquivo_limitado(arquivo, limite: int) -> bytes:
    """Lê ``arquivo`` em blocos e para assim que passa de ``limite`` bytes.

    Levanta ``ArquivoGrandeDemais`` sem carregar o restante. ``arquivo`` é um
    ``UploadFile`` (ou qualquer objeto com ``read(tamanho)`` assíncrono).
    """
    lido = bytearray()
    while True:
        bloco = await arquivo.read(TAMANHO_BLOCO)
        if not bloco:
            return bytes(lido)
        lido.extend(bloco)
        if len(lido) > limite:
            raise ArquivoGrandeDemais()


class LimiteCorpoUploadMiddleware:
    """Recusa com 413 o upload cujo corpo passa do limite, sem lê-lo inteiro."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            scope["type"] != "http"
            or scope["method"] != "POST"
            or scope["path"].rstrip("/") != ROTA_UPLOAD
        ):
            await self.app(scope, receive, send)
            return

        limite = limite_do_corpo()
        resposta_413 = JSONResponse(corpo_413(), status_code=413)

        declarado = dict(scope["headers"]).get(b"content-length")
        if declarado is not None and declarado.isdigit() and int(declarado) > limite:
            await resposta_413(scope, receive, send)
            return

        recebidos = 0
        excedeu = False
        respondeu = False

        async def receber() -> Message:
            nonlocal recebidos, excedeu
            if excedeu:
                return {"type": "http.disconnect"}
            mensagem = await receive()
            if mensagem["type"] == "http.request":
                recebidos += len(mensagem.get("body", b""))
                if recebidos > limite:
                    # Corta a leitura: o app vê o cliente "desconectar" e falha;
                    # a resposta dele é trocada pelo 413 em enviar().
                    excedeu = True
                    return {"type": "http.disconnect"}
            return mensagem

        async def enviar(mensagem: Message) -> None:
            nonlocal respondeu
            if not excedeu:
                await send(mensagem)
                return
            if not respondeu:
                respondeu = True
                await resposta_413(scope, receive, send)

        try:
            await self.app(scope, receber, enviar)
        except Exception:
            if not excedeu:
                raise
            # A falha veio do corte da leitura: a resposta correta é o 413.
        if excedeu and not respondeu:
            await resposta_413(scope, receive, send)
