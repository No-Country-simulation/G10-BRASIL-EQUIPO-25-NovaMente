"""Limite de requisições por chave, com janela deslizante em memória.

Cada chave guarda os instantes das requisições aceitas na última janela.
As chaves ficam numa ``OrderedDict`` na ordem do último uso: a cada chamada,
as do começo que estão ociosas há mais de uma janela são descartadas, e
acima de ``max_chaves`` as menos usadas saem mesmo ativas (o que só alivia o
limite delas). Assim a memória não cresce sem fim com muitos alunos.

Em memória e por processo: com vários workers, cada um conta à parte.
"""

from __future__ import annotations

import math
import threading
import time
from collections import OrderedDict, deque
from collections.abc import Callable

MAX_CHAVES_PADRAO = 10_000


class LimiteDeTaxa:
    """``limite`` requisições por ``janela_segundos`` em cada chave.

    ``limite`` pode ser um número ou uma função lida a cada chamada (para
    acompanhar a configuração); ``relogio`` pode ser injetado nos testes.
    """

    def __init__(
        self,
        limite: int | Callable[[], int],
        *,
        janela_segundos: float = 60.0,
        relogio: Callable[[], float] = time.monotonic,
        max_chaves: int = MAX_CHAVES_PADRAO,
    ):
        self._limite = limite
        self.janela = janela_segundos
        self.relogio = relogio
        self.max_chaves = max_chaves
        self._chaves: OrderedDict[str, deque[float]] = OrderedDict()
        self._trava = threading.Lock()

    def _limite_atual(self) -> int:
        valor = self._limite() if callable(self._limite) else self._limite
        return max(1, int(valor))

    def _descartar_ociosas(self, agora: float) -> None:
        while self._chaves:
            chave, instantes = next(iter(self._chaves.items()))
            if instantes and instantes[-1] > agora - self.janela:
                break
            del self._chaves[chave]

    def registrar(self, chave: str) -> float | None:
        """Conta a requisição e devolve ``None``; se passou do limite, não conta e
        devolve os segundos até a próxima ser aceita."""
        with self._trava:
            agora = self.relogio()
            self._descartar_ociosas(agora)
            instantes = self._chaves.get(chave)
            if instantes is None:
                instantes = self._chaves[chave] = deque()
            else:
                self._chaves.move_to_end(chave)
            while instantes and instantes[0] <= agora - self.janela:
                instantes.popleft()
            limite = self._limite_atual()
            if len(instantes) >= limite:
                return max(0.0, instantes[0] + self.janela - agora)
            instantes.append(agora)
            while len(self._chaves) > self.max_chaves:
                self._chaves.popitem(last=False)
            return None

    def limpar(self) -> None:
        with self._trava:
            self._chaves.clear()

    def __len__(self) -> int:
        with self._trava:
            return len(self._chaves)


def segundos_para_cabecalho(espera: float) -> int:
    """Valor de ``Retry-After``: segundos inteiros, arredondados para cima, no mínimo 1."""
    return max(1, math.ceil(espera))
