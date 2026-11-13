"""Adaptador do Gemini para ``ProvedorLLM``, sobre o SDK ``google-genai``.

O cliente é criado uma única vez, na primeira geração, e reaproveitado entre
jobs. O timeout vale por chamada (``HttpOptions`` no ``GenerateContentConfig``)
e o cliente não tem retentativa interna. A chave vem de ``GOOGLE_API_KEY``,
a mesma fonte dos embeddings; sem chave, a geração falha com
``ErroConfiguracao`` (a subida do app não depende dela).
"""

from __future__ import annotations

import logging
import os
import threading

from app.llm.base import Mensagem
from app.llm.erros import (
    ErroConfiguracao,
    ErroIndisponivel,
    ErroLimiteTaxa,
    ErroLLM,
    ErroRespostaInvalida,
    ErroTimeout,
)

logger = logging.getLogger(__name__)

# Mesmos códigos que app/rag/embeddings.py trata como configuração.
_CODIGOS_CONFIGURACAO = {400, 401, 403, 404}
_PAPEIS_SDK = {"user": "user", "assistant": "model"}


def _cadeia(erro: BaseException):
    """Percorre a exceção e as que a causaram (__cause__, depois __context__)."""
    vistos: set[int] = set()
    atual: BaseException | None = erro
    while atual is not None and id(atual) not in vistos:
        vistos.add(id(atual))
        yield atual
        atual = atual.__cause__ or atual.__context__


def _categoria_por_tipo(erro: BaseException) -> type[ErroLLM] | None:
    import httpx
    from google.genai import errors as genai_errors

    try:
        import httpx2  # alternativa ao httpx suportada pelo SDK
    except ImportError:
        httpx2 = None

    if isinstance(erro, genai_errors.APIError):
        codigo = erro.code
        if codigo == 429:
            return ErroLimiteTaxa
        if codigo in (408, 504):  # 504: DeadlineExceeded no SDK antigo
            return ErroTimeout
        if codigo in _CODIGOS_CONFIGURACAO:
            return ErroConfiguracao
        return ErroIndisponivel  # 5xx e demais erros da API
    if isinstance(erro, (httpx.TimeoutException, TimeoutError)):
        return ErroTimeout
    if httpx2 is not None and isinstance(erro, httpx2.TimeoutException):
        return ErroTimeout
    if isinstance(erro, (httpx.TransportError, ConnectionError)):
        return ErroIndisponivel
    if httpx2 is not None and isinstance(erro, httpx2.TransportError):
        return ErroIndisponivel
    return None


def classificar_erro(erro: BaseException) -> type[ErroLLM]:
    """Categoria normalizada de uma exceção levantada pelo SDK.

    Vale a primeira exceção reconhecida na cadeia; o que não for reconhecido
    vira ``ErroLLM`` (o pipeline trata como erro interno).
    """
    for item in _cadeia(erro):
        categoria = _categoria_por_tipo(item)
        if categoria is not None:
            return categoria
    return ErroLLM


def _resumo(erro: BaseException) -> str:
    """Tipos e códigos da cadeia, para log (sem a mensagem, que pode ter dados)."""
    partes = []
    for item in _cadeia(erro):
        codigo = getattr(item, "code", None)
        partes.append(f"{type(item).__name__}({codigo})" if codigo else type(item).__name__)
    return " <- ".join(partes)


class ProvedorGemini:
    """Gera texto com o Gemini via ``google-genai``."""

    nome = "gemini"

    def __init__(self, modelo: str):
        self.modelo = modelo
        self._cliente = None
        self._trava = threading.Lock()

    def _obter_cliente(self):
        if self._cliente is not None:
            return self._cliente
        with self._trava:
            if self._cliente is None:
                chave = os.getenv("GOOGLE_API_KEY")
                if not chave:
                    raise ErroConfiguracao("GOOGLE_API_KEY não definida.")
                from google.genai import Client

                try:
                    self._cliente = Client(api_key=chave)
                except Exception as exc:
                    raise ErroConfiguracao(
                        f"Não foi possível criar o cliente Gemini: {type(exc).__name__}"
                    ) from None
        return self._cliente

    @staticmethod
    def _montar(mensagens: list[Mensagem]) -> tuple[str | None, list]:
        """Separa as instruções de sistema e monta o conteúdo da conversa."""
        from google.genai import types

        sistema = [m.conteudo for m in mensagens if m.papel == "system"]
        conversa = [
            types.Content(role=_PAPEIS_SDK[m.papel], parts=[types.Part(text=m.conteudo)])
            for m in mensagens
            if m.papel != "system"
        ]
        return ("\n\n".join(sistema) if sistema else None), conversa

    def gerar(self, mensagens: list[Mensagem], *, timeout_segundos: float) -> str:
        from google.genai import types

        cliente = self._obter_cliente()
        sistema, conversa = self._montar(mensagens)
        configuracao = types.GenerateContentConfig(
            system_instruction=sistema,
            http_options=types.HttpOptions(timeout=int(timeout_segundos * 1000)),
        )
        try:
            resposta = cliente.models.generate_content(
                model=self.modelo, contents=conversa, config=configuracao
            )
        except Exception as exc:
            categoria = classificar_erro(exc)
            logger.error("Falha na chamada ao Gemini (%s): %s", categoria.__name__, _resumo(exc))
            raise categoria(_resumo(exc)) from None

        try:
            texto = resposta.text
        except Exception as exc:  # o SDK pode recusar o acesso ao texto
            raise ErroRespostaInvalida(f"Resposta sem texto: {type(exc).__name__}") from None
        if not texto or not texto.strip():
            raise ErroRespostaInvalida("Resposta vazia ou bloqueada.")
        return texto
