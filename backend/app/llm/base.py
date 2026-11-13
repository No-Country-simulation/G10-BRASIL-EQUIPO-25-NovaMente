"""Contrato dos provedores de LLM: mensagens de entrada e o método de geração."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol, runtime_checkable

PapelMensagem = Literal["system", "user", "assistant"]


@dataclass(frozen=True)
class Mensagem:
    """Uma mensagem da conversa enviada ao modelo."""

    papel: PapelMensagem
    conteudo: str


@runtime_checkable
class ProvedorLLM(Protocol):
    """Interface que todo provedor de LLM implementa.

    ``gerar`` recebe a conversa inteira (lista de mensagens, para que um chat
    use o mesmo contrato) e devolve só o texto da resposta. Falhas sobem
    apenas como as exceções de ``app.llm.erros``; nenhum erro de SDK vaza.
    """

    nome: str

    def gerar(self, mensagens: list[Mensagem], *, timeout_segundos: float) -> str:
        """Gera a resposta do modelo para ``mensagens`` em até ``timeout_segundos``."""
        ...
