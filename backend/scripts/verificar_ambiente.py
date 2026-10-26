"""Verifica, com a chave real, as premissas do módulo RAG.

1. Métrica cosseno numa collection do Chroma (configuração `hnsw.space`).
2. `task_type` RETRIEVAL_DOCUMENT / RETRIEVAL_QUERY no gemini-embedding-001.

Uso (no container): python backend/scripts/verificar_ambiente.py
Lê GOOGLE_API_KEY do ambiente e nunca a imprime. O Chroma usado aqui é
em memória, nada é gravado em disco.
"""

import math
import os
import sys

import chromadb
from langchain_google_genai import GoogleGenerativeAIEmbeddings

MODELO = "models/gemini-embedding-001"


def cosseno(a: list[float], b: list[float]) -> float:
    num = sum(x * y for x, y in zip(a, b))
    return num / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)))


def verificar_chroma() -> None:
    cliente = chromadb.EphemeralClient()
    col = cliente.create_collection(
        "verificacao_cosseno",
        configuration={"hnsw": {"space": "cosine"}},
        embedding_function=None,
    )
    print("[chroma] configuração:", col.configuration_json.get("hnsw"))
    col.add(ids=["a", "b"], embeddings=[[1.0, 0.0], [0.0, 1.0]])
    r = col.query(query_embeddings=[[1.0, 1.0]], n_results=2)
    print("[chroma] distâncias para [1,1] (esperado ~0,2929 cada):", r["distances"][0])


def verificar_gemini() -> None:
    if not os.getenv("GOOGLE_API_KEY"):
        sys.exit("GOOGLE_API_KEY não definida no ambiente.")
    emb = GoogleGenerativeAIEmbeddings(model=MODELO)
    docs = [
        "O código HTTP 404 indica que o recurso não foi encontrado no servidor.",
        "A fotossíntese converte luz em energia química nas plantas.",
    ]
    pergunta = "O que significa o erro 404?"

    v_doc = emb.embed_documents(docs, task_type="RETRIEVAL_DOCUMENT")
    v_q = emb.embed_query(pergunta, task_type="RETRIEVAL_QUERY")
    v_q_sem = emb.embed_query(pergunta)
    v_q_doc = emb.embed_query(pergunta, task_type="RETRIEVAL_DOCUMENT")

    print("[gemini] dimensões:", len(v_doc[0]), len(v_q))
    print("[gemini] cos(query, doc HTTP):", round(cosseno(v_q, v_doc[0]), 4))
    print("[gemini] cos(query, doc fotossíntese):", round(cosseno(v_q, v_doc[1]), 4))
    print("[gemini] cos(QUERY, sem task_type):", round(cosseno(v_q, v_q_sem), 6))
    print("[gemini] cos(QUERY, DOCUMENT) mesma frase:", round(cosseno(v_q, v_q_doc), 6))
    try:
        emb.embed_query(pergunta, task_type="TIPO_INEXISTENTE")
        print("[gemini] task_type inválido foi aceito (sem validação)")
    except Exception as erro:  # noqa: BLE001
        print("[gemini] task_type inválido rejeitado:", type(erro).__name__)


if __name__ == "__main__":
    verificar_chroma()
    verificar_gemini()
