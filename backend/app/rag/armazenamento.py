"""Persistência dos trechos no ChromaDB: uma collection por documento.

Separar por documento evita misturar fontes na recuperação. A collection usa
métrica cosseno; a relevância devolvida é 1 - distância, limitada a [0, 1].
Este módulo recebe vetores prontos; quem gera os embeddings é `embeddings.py`.
"""

import hashlib
import re

import chromadb
from chromadb.errors import NotFoundError

from app.rag import config
from app.rag.modelos import Trecho

_cliente: chromadb.ClientAPI | None = None


def definir_cliente(cliente: chromadb.ClientAPI | None) -> None:
    """Troca o cliente Chroma (usado nos testes com pasta temporária)."""
    global _cliente
    _cliente = cliente


def obter_cliente() -> chromadb.ClientAPI:
    global _cliente
    if _cliente is None:
        _cliente = chromadb.PersistentClient(path=config.CHROMA_DIR)
    return _cliente


def nome_collection(documento_id: str) -> str:
    """Converte o id do documento num nome válido de collection.

    O Chroma aceita só [a-zA-Z0-9._-], de 3 a 512 caracteres, começando e
    terminando com letra ou número. O hash no final evita colisão entre ids
    que ficariam iguais depois de limpos (ex.: "a b" e "a-b").
    """
    if not documento_id or not documento_id.strip():
        raise ValueError("O documento_id não pode ser vazio.")
    limpo = re.sub(r"[^a-zA-Z0-9_-]+", "-", documento_id.strip())[:40]
    resumo = hashlib.sha1(documento_id.encode("utf-8")).hexdigest()[:12]
    return f"{config.PREFIXO_COLLECTION}{limpo}_{resumo}"


def salvar_trechos(
    documento_id: str,
    titulo: str,
    trechos: list[str],
    vetores: list[list[float]],
) -> int:
    """Grava os trechos do documento, substituindo o que já existia."""
    if len(trechos) != len(vetores):
        raise ValueError("Quantidade de trechos e de vetores não confere.")
    cliente = obter_cliente()
    nome = nome_collection(documento_id)
    remover_documento(documento_id)
    colecao = cliente.create_collection(
        nome,
        configuration={"hnsw": {"space": config.METRICA}},
        metadata={"documento_id": documento_id, "titulo": titulo},
        embedding_function=None,
    )
    if trechos:
        colecao.add(
            ids=[f"{i:05d}" for i in range(len(trechos))],
            documents=trechos,
            embeddings=vetores,
            metadatas=[{"indice": i, "documento_id": documento_id} for i in range(len(trechos))],
        )
    return len(trechos)


def remover_documento(documento_id: str) -> bool:
    """Apaga a collection do documento. Devolve False se ela não existia."""
    try:
        obter_cliente().delete_collection(nome_collection(documento_id))
        return True
    except NotFoundError:
        return False


def buscar(documento_id: str, vetor_consulta: list[float], k: int = config.K_PADRAO) -> list[Trecho]:
    """Devolve os k trechos mais parecidos, do mais relevante ao menos.

    Levanta LookupError se o documento não foi indexado.
    """
    if k < 1:
        raise ValueError("k precisa ser pelo menos 1.")
    try:
        colecao = obter_cliente().get_collection(nome_collection(documento_id), embedding_function=None)
    except NotFoundError:
        raise LookupError(f"Documento não indexado: {documento_id}") from None
    total = colecao.count()
    if total == 0:
        return []
    r = colecao.query(
        query_embeddings=[vetor_consulta],
        n_results=min(k, total),
        include=["documents", "metadatas", "distances"],
    )
    return [
        Trecho(
            texto=texto,
            indice=int(meta["indice"]),
            relevancia=min(1.0, max(0.0, 1.0 - float(dist))),
            documento_id=documento_id,
        )
        for texto, meta, dist in zip(r["documents"][0], r["metadatas"][0], r["distances"][0])
    ]
