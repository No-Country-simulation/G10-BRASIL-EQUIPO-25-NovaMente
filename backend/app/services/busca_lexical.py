"""Busca lexical BM25 (Okapi) em Python puro, determinística.

Tokenização: minúsculas e sem acento (``ancoragem.normalizar``), só letras e
dígitos, sem stopwords do português e sem tokens de 1 caractere. O plural
simples é tirado (``ancoragem.singular``), para "métodos" achar "método".
Nada aqui altera o comportamento do ``ancoragem``: só as funções puras dele
são reaproveitadas.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Sequence

from app.services.ancoragem import STOPWORDS as _STOPWORDS_LONGAS
from app.services.ancoragem import normalizar, singular

K1 = 1.5
B = 0.75

_TOKEN = re.compile(r"[a-z0-9]+")

# Palavras funcionais curtas (as de 4 letras ou mais vêm do ancoragem).
_STOPWORDS_CURTAS = frozenset(
    """
    de da do das dos a o as os e em no na nos nas um uma uns umas ao aos que
    se por com sem para pra mas ou nao sim eu tu ele ela nos vos lhe lhes me
    te seu sua meu teu ja so ate tem ter ser sao foi era sob tal tao
    qual como isso este esta esse essa pelo pela mais
    """.split()
)
STOPWORDS: frozenset[str] = _STOPWORDS_CURTAS | _STOPWORDS_LONGAS


def tokenizar(texto: str) -> list[str]:
    """Tokens da busca, na ordem do texto (com repetição)."""
    tokens = []
    for token in _TOKEN.findall(normalizar(texto)):
        if len(token) < 2 or token in STOPWORDS:
            continue
        tokens.append(singular(token))
    return tokens


class IndiceBM25:
    """Índice de uma lista de trechos ``(id, texto)``, reutilizável entre buscas.

    Guarda só a frequência dos termos por trecho, o tamanho de cada trecho e
    o número de trechos em que cada termo aparece (df).
    """

    def __init__(self, trechos: Sequence[tuple[str, str]], *, k1: float = K1, b: float = B):
        self.trechos = list(trechos)
        self.k1 = k1
        self.b = b
        self._frequencias: list[Counter[str]] = []
        self._tamanhos: list[int] = []
        df: Counter[str] = Counter()
        for _id, texto in self.trechos:
            frequencia = Counter(tokenizar(texto))
            self._frequencias.append(frequencia)
            self._tamanhos.append(sum(frequencia.values()))
            df.update(frequencia.keys())
        total = len(self.trechos)
        self._media_tamanho = (sum(self._tamanhos) / total) if total else 0.0
        # idf do BM25 com +1 dentro do log (sempre positivo, como no Lucene).
        self._idf = {
            termo: math.log(1 + (total - n + 0.5) / (n + 0.5)) for termo, n in df.items()
        }

    def __len__(self) -> int:
        return len(self.trechos)

    def pontuar(self, consulta: str) -> list[float]:
        """Pontuação BM25 de cada trecho, na ordem original."""
        termos = list(dict.fromkeys(tokenizar(consulta)))  # cada termo da consulta uma vez
        pontuacoes = [0.0] * len(self.trechos)
        if not termos or not self.trechos:
            return pontuacoes
        media = self._media_tamanho or 1.0
        for posicao, frequencia in enumerate(self._frequencias):
            normalizacao = self.k1 * (1 - self.b + self.b * self._tamanhos[posicao] / media)
            total = 0.0
            for termo in termos:
                tf = frequencia.get(termo)
                if tf:
                    total += self._idf[termo] * tf * (self.k1 + 1) / (tf + normalizacao)
            pontuacoes[posicao] = total
        return pontuacoes

    def buscar(self, consulta: str, k: int | None = None) -> list[tuple[tuple[str, str], float]]:
        """``(trecho, pontuação)`` com pontuação > 0, da maior para a menor.

        Empates ficam na ordem original dos trechos. ``k`` limita o resultado.
        """
        pontuacoes = self.pontuar(consulta)
        ordem = sorted(
            (p for p in range(len(pontuacoes)) if pontuacoes[p] > 0),
            key=lambda p: (-pontuacoes[p], p),
        )
        if k is not None:
            ordem = ordem[: max(0, k)]
        return [(self.trechos[p], pontuacoes[p]) for p in ordem]
