"""Provedor do chat: prazo total por pergunta e no máximo uma retentativa.

O chat responde dentro de uma requisição HTTP, fora de qualquer job, então
não usa ``ProvedorComRetentativa`` (que lê ``LLM_TENTATIVAS`` e o prazo do job
em ``limites_da_geracao``). Aqui:

- ``timeout_segundos`` de ``gerar`` é o prazo TOTAL da pergunta (a fábrica
  sugere ``CHAT_LLM_TIMEOUT_SEGUNDOS``), não o de cada chamada: cada chamada
  recebe só o tempo que ainda resta;
- só ``ErroTransitorio`` (429, 5xx, falha de conexão) e ``ErroTimeout`` são
  repetidos, uma vez, e só se depois da espera ainda sobrar
  ``CHAMADA_MINIMA_SEGUNDOS``; o resto (chave, modelo indisponível, resposta
  inválida) sobe na primeira vez;
- nenhum estado é compartilhado com os jobs: o prazo vive em variáveis locais
  de cada chamada e o ``ContextVar`` da geração não é lido nem alterado.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from app.llm import retentativa
from app.llm.base import Mensagem, ProvedorLLM
from app.llm.erros import ErroTimeout, ErroTransitorio

logger = logging.getLogger(__name__)

TENTATIVAS_CHAT = 2  # a primeira chamada e no máximo uma retentativa
ESPERA_CHAT_SEGUNDOS = 1.0  # antes da retentativa (com o mesmo jitter da geração)
CHAMADA_MINIMA_SEGUNDOS = 3.0  # menos que isto não vale uma nova chamada

_RETENTAVEIS = (ErroTransitorio, ErroTimeout)


class ProvedorDoChat:
    """``ProvedorLLM`` do chat sobre um provedor ``base`` (sem retentativa própria).

    Relógio, sono e sorteio padrão são os de ``app.llm.retentativa``, lidos a
    cada chamada (os testes trocam por versões falsas); também podem ser
    injetados.
    """

    def __init__(
        self,
        base: ProvedorLLM,
        *,
        relogio: Callable[[], float] | None = None,
        dormir: Callable[[float], None] | None = None,
        sortear: Callable[[float, float], float] | None = None,
    ):
        self.base = base
        self.nome = base.nome
        self._relogio = relogio
        self._dormir = dormir
        self._sortear = sortear

    def __repr__(self) -> str:
        return f"ProvedorDoChat({self.base!r})"

    def gerar(self, mensagens: list[Mensagem], *, timeout_segundos: float) -> str:
        relogio = self._relogio or retentativa._relogio
        fim = relogio() + timeout_segundos
        tentativa = 1
        while True:
            restante = fim - relogio()
            if restante <= 0:
                raise ErroTimeout("Prazo da pergunta esgotado antes da chamada ao modelo.")
            try:
                return self.base.gerar(mensagens, timeout_segundos=restante)
            except _RETENTAVEIS as erro:
                categoria = type(erro).__name__
                espera = ESPERA_CHAT_SEGUNDOS * (self._sortear or retentativa._sortear)(
                    1 - retentativa.JITTER, 1 + retentativa.JITTER
                )
                sobra = fim - relogio() - espera
                if tentativa >= TENTATIVAS_CHAT or sobra < CHAMADA_MINIMA_SEGUNDOS:
                    logger.warning(
                        "Falha transitória no chat %s (%s, tentativa %d de %d); sem nova tentativa.",
                        self.nome, categoria, tentativa, TENTATIVAS_CHAT,
                    )
                    raise
                logger.warning(
                    "Falha transitória no chat %s (%s); nova tentativa em %.1fs.",
                    self.nome, categoria, espera,
                )
                (self._dormir or retentativa._dormir)(espera)
                tentativa += 1
