"""Persistência dos trechos no ChromaDB: uma collection única para todos os documentos.

Cada trecho é uma linha com id ``"<documento_id>:<indice>"`` e metadados
``documento_id``, ``indice`` e ``titulo``; a busca filtra por
``documento_id``, então fontes diferentes não se misturam. A collection usa
métrica cosseno; a relevância devolvida é 1 - distância, limitada a [0, 1].
Este módulo recebe vetores prontos; quem gera os embeddings é `embeddings.py`.

Por que uma collection só: neste Chroma, apagar uma collection não remove do
disco o diretório do índice HNSW, nem libera a memória do processo; apagar as
linhas de um documento numa collection única cresce cerca de 10 vezes menos.
"""

import threading

import chromadb

from app.rag import config
from app.rag.modelos import Trecho

_cliente: chromadb.ClientAPI | None = None
# Protege a troca do cliente e a criação da collection: vários jobs rodam em threads.
_trava = threading.RLock()
_LOTE_LEITURA = 1000  # linhas por página ao listar a collection inteira


def definir_cliente(cliente: chromadb.ClientAPI | None) -> None:
    """Troca o cliente Chroma (usado nos testes com pasta temporária)."""
    global _cliente
    with _trava:
        _cliente = cliente


def cliente_atual() -> chromadb.ClientAPI | None:
    """Cliente já criado ou injetado, sem criar um novo (nem a pasta do Chroma)."""
    return _cliente


def obter_cliente() -> chromadb.ClientAPI:
    global _cliente
    with _trava:
        if _cliente is None:
            _cliente = chromadb.PersistentClient(path=config.CHROMA_DIR)
        return _cliente


def validar_documento_id(documento_id: str) -> None:
    """Levanta ValueError se o id do documento for vazio."""
    if not documento_id or not documento_id.strip():
        raise ValueError("O documento_id não pode ser vazio.")


def _colecao():
    """A collection compartilhada, criada na primeira vez (com segurança entre threads)."""
    with _trava:
        return obter_cliente().get_or_create_collection(
            config.NOME_COLLECTION,
            configuration={"hnsw": {"space": config.METRICA}},
            embedding_function=None,
        )


def _filtro(documento_id: str) -> dict:
    return {"documento_id": documento_id}


def _ids_do_documento(colecao, documento_id: str) -> list[str]:
    return colecao.get(where=_filtro(documento_id), include=[])["ids"]


def salvar_trechos(
    documento_id: str,
    titulo: str,
    trechos: list[str],
    vetores: list[list[float]],
) -> int:
    """Grava os trechos do documento, substituindo o que já existia dele."""
    validar_documento_id(documento_id)
    if len(trechos) != len(vetores):
        raise ValueError("Quantidade de trechos e de vetores não confere.")
    colecao = _colecao()
    colecao.delete(where=_filtro(documento_id))
    if trechos:
        colecao.add(
            ids=[f"{documento_id}:{i:05d}" for i in range(len(trechos))],
            documents=trechos,
            embeddings=vetores,
            metadatas=[
                {"documento_id": documento_id, "indice": i, "titulo": titulo}
                for i in range(len(trechos))
            ],
        )
    return len(trechos)


def existe_documento(documento_id: str) -> bool:
    validar_documento_id(documento_id)
    return bool(_ids_do_documento(_colecao(), documento_id))


def remover_documento(documento_id: str) -> bool:
    """Apaga as linhas do documento. Devolve False se não havia nenhuma."""
    validar_documento_id(documento_id)
    colecao = _colecao()
    ids = _ids_do_documento(colecao, documento_id)
    if not ids:
        return False
    colecao.delete(ids=ids)
    return True


def documentos_indexados() -> dict[str, int]:
    """Quantas linhas cada ``documento_id`` tem na collection (sem ler os vetores)."""
    colecao = _colecao()
    contagem: dict[str, int] = {}
    inicio = 0
    while True:
        pagina = colecao.get(include=["metadatas"], limit=_LOTE_LEITURA, offset=inicio)
        for meta in pagina["metadatas"]:
            documento_id = (meta or {}).get("documento_id")
            if isinstance(documento_id, str):
                contagem[documento_id] = contagem.get(documento_id, 0) + 1
        if len(pagina["ids"]) < _LOTE_LEITURA:
            return contagem
        inicio += _LOTE_LEITURA


def buscar(documento_id: str, vetor_consulta: list[float], k: int = config.K_PADRAO) -> list[Trecho]:
    """Devolve os k trechos do documento mais parecidos, do mais relevante ao menos.

    Levanta LookupError se o documento não foi indexado.
    """
    validar_documento_id(documento_id)
    if k < 1:
        raise ValueError("k precisa ser pelo menos 1.")
    colecao = _colecao()
    total = len(_ids_do_documento(colecao, documento_id))
    if total == 0:
        raise LookupError(f"Documento não indexado: {documento_id}")
    r = colecao.query(
        query_embeddings=[vetor_consulta],
        n_results=min(k, total),
        where=_filtro(documento_id),
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
