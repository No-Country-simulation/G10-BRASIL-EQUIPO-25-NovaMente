"""Embedding falso e determinístico para os testes (sem rede).

Cada palavra vira uma posição do vetor via hash; textos com palavras em comum
ficam próximos no cosseno.
"""

import hashlib
import re

from langchain_core.embeddings import Embeddings

DIMENSOES = 64


def _vetor(texto: str) -> list[float]:
    v = [0.0] * DIMENSOES
    for palavra in re.findall(r"\w+", texto.lower()):
        h = int(hashlib.md5(palavra.encode()).hexdigest(), 16)
        v[h % DIMENSOES] += 1.0
    if not any(v):
        v[0] = 1.0
    return v


class EmbeddingFalso(Embeddings):
    def __init__(self):
        self.chamadas: list[tuple[str, int, str | None]] = []

    def embed_documents(self, texts, task_type=None, **_):
        self.chamadas.append(("documentos", len(texts), task_type))
        return [_vetor(t) for t in texts]

    def embed_query(self, text, task_type=None, **_):
        self.chamadas.append(("consulta", 1, task_type))
        return _vetor(text)
