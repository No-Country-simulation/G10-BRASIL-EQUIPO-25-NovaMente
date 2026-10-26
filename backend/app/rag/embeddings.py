"""Geração de embeddings (Gemini) com ponto de injeção para testes.

Por padrão usa `gemini-embedding-001` via langchain-google-genai, com a chave
lida de GOOGLE_API_KEY. Os testes chamam `definir_embeddings` com um modelo
falso e não acessam a rede.

O modelo injetado precisa seguir a interface `Embeddings` do LangChain e
aceitar o argumento nomeado `task_type` em `embed_documents`/`embed_query`.
"""

import time

from langchain_core.embeddings import Embeddings

from app.rag import config

_modelo: Embeddings | None = None


def criar_embeddings_gemini() -> Embeddings:
    """Cria o cliente Gemini. Falha se GOOGLE_API_KEY não estiver definida."""
    from langchain_google_genai import GoogleGenerativeAIEmbeddings

    return GoogleGenerativeAIEmbeddings(model=config.MODELO_EMBEDDING)


def definir_embeddings(modelo: Embeddings | None) -> None:
    """Troca o modelo de embeddings (None volta ao Gemini na próxima chamada)."""
    global _modelo
    _modelo = modelo


def obter_embeddings() -> Embeddings:
    global _modelo
    if _modelo is None:
        _modelo = criar_embeddings_gemini()
    return _modelo


def _eh_limite_de_taxa(erro: Exception) -> bool:
    texto = str(erro)
    return "429" in texto or "RESOURCE_EXHAUSTED" in texto


def _com_retentativa(funcao, *args, **kwargs):
    espera = config.EMBEDDING_ESPERA_INICIAL
    for tentativa in range(1, config.EMBEDDING_TENTATIVAS + 1):
        try:
            return funcao(*args, **kwargs)
        except Exception as erro:
            if not _eh_limite_de_taxa(erro) or tentativa == config.EMBEDDING_TENTATIVAS:
                raise
            time.sleep(espera)
            espera *= 2


def vetorizar_trechos(textos: list[str]) -> list[list[float]]:
    """Embeddings dos trechos do documento (task_type RETRIEVAL_DOCUMENT), em lotes."""
    modelo = obter_embeddings()
    vetores: list[list[float]] = []
    for inicio in range(0, len(textos), config.EMBEDDING_LOTE):
        lote = textos[inicio : inicio + config.EMBEDDING_LOTE]
        vetores.extend(
            _com_retentativa(
                modelo.embed_documents, lote, task_type=config.TASK_TYPE_DOCUMENTO
            )
        )
    return vetores


def vetorizar_consulta(texto: str) -> list[float]:
    """Embedding da pergunta (task_type RETRIEVAL_QUERY)."""
    return _com_retentativa(
        obter_embeddings().embed_query, texto, task_type=config.TASK_TYPE_CONSULTA
    )
