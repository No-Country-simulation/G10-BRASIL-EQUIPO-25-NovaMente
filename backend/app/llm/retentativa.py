"""Retentativa com backoff exponencial e jitter sobre qualquer ``ProvedorLLM``.

``ProvedorComRetentativa`` embrulha o provedor escolhido pela fábrica e
retenta só as falhas transitórias normalizadas: ``ErroTransitorio`` (limite
de uso e indisponibilidade) e ``ErroTimeout``. ``ErroConfiguracao`` sobe na
primeira vez, e ``ErroRespostaInvalida`` também, porque o pipeline já a
retenta (retentar aqui multiplicaria as chamadas).

O prazo do job e o cancelamento chegam por ``limites_da_geracao``, aberto
pelo pipeline na thread do job:

- nenhuma retentativa começa se a espera mais uma chamada inteira
  (``timeout_segundos``) não couberem no prazo restante; nesse caso o último
  erro sobe como está;
- a espera é dormida em fatias curtas e, entre elas, ``verificar_interrupcao``
  pode interromper o job (cancelamento pelo usuário).
"""

from __future__ import annotations

import logging
import random
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass

from app.core.config import settings
from app.llm.base import Mensagem, ProvedorLLM
from app.llm.erros import ErroTimeout, ErroTransitorio

logger = logging.getLogger(__name__)

ESPERA_MAXIMA_SEGUNDOS = 30.0  # teto de cada espera, já com o jitter
JITTER = 0.2  # variação aleatória de ±20% em cada espera (como nos embeddings)
FATIA_ESPERA_SEGUNDOS = 0.5  # intervalo entre as checagens de cancelamento na espera

_RETENTAVEIS = (ErroTransitorio, ErroTimeout)

# Relógio, sono e sorteio padrão; os testes trocam por versões falsas.
_relogio: Callable[[], float] = time.monotonic
_dormir: Callable[[float], None] = time.sleep
_sortear: Callable[[float, float], float] = random.uniform


@dataclass(frozen=True)
class LimitesGeracao:
    """Prazo e interrupção do job em andamento nesta thread."""

    prazo: float | None = None  # instante de ``time.monotonic()`` em que o job expira
    verificar_interrupcao: Callable[[], None] | None = None  # levanta se o job parou


_limites: ContextVar[LimitesGeracao] = ContextVar("limites_geracao", default=LimitesGeracao())


@contextmanager
def limites_da_geracao(
    prazo: float | None = None,
    verificar_interrupcao: Callable[[], None] | None = None,
) -> Iterator[None]:
    """Vale para as chamadas ao LLM feitas dentro do bloco, nesta thread."""
    token = _limites.set(LimitesGeracao(prazo, verificar_interrupcao))
    try:
        yield
    finally:
        _limites.reset(token)


def calcular_espera(tentativa: int, espera_inicial: float, fator_jitter: float) -> float:
    """Espera depois da falha da ``tentativa`` (1, 2, ...): dobra a cada vez, com teto."""
    return min(espera_inicial * 2 ** (tentativa - 1) * fator_jitter, ESPERA_MAXIMA_SEGUNDOS)


class ProvedorComRetentativa:
    """``ProvedorLLM`` que repete as falhas transitórias do provedor ``base``.

    Lê ``settings.llm_tentativas`` e ``settings.llm_espera_inicial_segundos``
    a cada geração. Relógio, sono e sorteio podem ser injetados (testes).
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

    def _agora(self) -> float:
        return (self._relogio or _relogio)()

    def _fator_jitter(self) -> float:
        return (self._sortear or _sortear)(1 - JITTER, 1 + JITTER)

    def _esperar(self, segundos: float, verificar: Callable[[], None] | None) -> None:
        dormir = self._dormir or _dormir
        restante = segundos
        while restante > 0:
            if verificar:
                verificar()
            fatia = min(restante, FATIA_ESPERA_SEGUNDOS)
            dormir(fatia)
            restante -= fatia
        if verificar:
            verificar()

    def gerar(self, mensagens: list[Mensagem], *, timeout_segundos: float) -> str:
        tentativas = max(1, settings.llm_tentativas)
        espera_inicial = max(0.0, settings.llm_espera_inicial_segundos)
        limites = _limites.get()
        tentativa = 1
        while True:
            try:
                return self.base.gerar(mensagens, timeout_segundos=timeout_segundos)
            except _RETENTAVEIS as erro:
                categoria = type(erro).__name__
                if tentativa >= tentativas:
                    logger.warning(
                        "Falha transitória no LLM %s (%s, tentativa %d de %d); "
                        "tentativas esgotadas.",
                        self.nome, categoria, tentativa, tentativas,
                    )
                    raise
                espera = calcular_espera(tentativa, espera_inicial, self._fator_jitter())
                if (
                    limites.prazo is not None
                    and self._agora() + espera + timeout_segundos > limites.prazo
                ):
                    logger.warning(
                        "Falha transitória no LLM %s (%s, tentativa %d de %d); "
                        "o prazo do job não comporta outra chamada.",
                        self.nome, categoria, tentativa, tentativas,
                    )
                    raise
                logger.warning(
                    "Falha transitória no LLM %s (%s, tentativa %d de %d); "
                    "nova tentativa em %.1fs.",
                    self.nome, categoria, tentativa, tentativas, espera,
                )
                self._esperar(espera, limites.verificar_interrupcao)
                tentativa += 1
