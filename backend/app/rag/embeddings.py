"""Geração de embeddings (Gemini) com ponto de injeção para testes.

Por padrão usa `gemini-embedding-001` via SDK `google-genai`, com a chave
lida de GOOGLE_API_KEY. Os testes chamam `definir_embeddings` com um modelo
falso e não acessam a rede.

O modelo injetado precisa seguir a interface `Embeddings` do LangChain e
aceitar o argumento nomeado `task_type` em `embed_documents`/`embed_query`.

Cada chamada tem timeout (`EMBEDDING_TIMEOUT_SEGUNDOS`). Falhas transitórias
(limite de taxa, indisponibilidade, timeout, conexão) são retentadas com
espera exponencial e jitter; erros de configuração falham na hora. Em ambos
os casos o erro final é um RuntimeError com mensagem em português.
"""

import logging
import os
import random
import time

from langchain_core.embeddings import Embeddings

from app.rag import config

logger = logging.getLogger(__name__)

_modelo: Embeddings | None = None

_TIMEOUT = "timeout"
_LIMITE_DE_TAXA = "limite_de_taxa"
_INDISPONIVEL = "indisponivel"
_CONFIGURACAO = "configuracao"

_MENSAGENS = {
    _TIMEOUT: "O serviço de embeddings demorou demais para responder. Tente novamente.",
    _LIMITE_DE_TAXA: (
        "O limite de uso do serviço de embeddings foi atingido. "
        "Tente novamente em alguns minutos."
    ),
    _INDISPONIVEL: (
        "O serviço de embeddings está indisponível no momento. "
        "Tente novamente em instantes."
    ),
    _CONFIGURACAO: (
        "O serviço de embeddings não está configurado corretamente "
        "(modelo ou chave de API). Avise a equipe."
    ),
}

_CODIGOS_CONFIGURACAO = {400, 401, 403, 404}


class EmbeddingsGemini(Embeddings):
    """Embeddings do Gemini usando o SDK `google-genai` diretamente.

    O cliente tem timeout por chamada (`EMBEDDING_TIMEOUT_SEGUNDOS`) e nenhuma
    retentativa interna: quem retenta é `_com_retentativa`. As exceções do SDK
    sobem sem embrulho, para serem classificadas pelo tipo.
    """

    def __init__(self, modelo: str, chave: str, timeout_segundos: float):
        from google.genai import Client
        from google.genai.types import HttpOptions

        self.modelo = modelo
        self._cliente = Client(
            api_key=chave,
            http_options=HttpOptions(timeout=int(timeout_segundos * 1000)),
        )

    def _vetorizar(self, textos: list[str], task_type: str | None) -> list[list[float]]:
        from google.genai.types import EmbedContentConfig

        resposta = self._cliente.models.embed_content(
            model=self.modelo,
            contents=[{"parts": [{"text": texto}]} for texto in textos],
            config=EmbedContentConfig(task_type=task_type),
        )
        return [list(item.values) for item in resposta.embeddings]

    def embed_documents(self, texts: list[str], task_type: str | None = None) -> list[list[float]]:
        if not texts:
            return []
        return self._vetorizar(texts, task_type)

    def embed_query(self, text: str, task_type: str | None = None) -> list[float]:
        return self._vetorizar([text], task_type)[0]


def criar_embeddings_gemini() -> Embeddings:
    """Cria o cliente Gemini. Levanta ValueError se GOOGLE_API_KEY não estiver definida."""
    chave = os.getenv("GOOGLE_API_KEY")
    if not chave:
        raise ValueError(
            "GOOGLE_API_KEY não definida: configure a chave do Gemini no ambiente."
        )
    return EmbeddingsGemini(
        modelo=config.MODELO_EMBEDDING,
        chave=chave,
        timeout_segundos=config.EMBEDDING_TIMEOUT_SEGUNDOS,
    )


def definir_embeddings(modelo: Embeddings | None) -> None:
    """Troca o modelo de embeddings (None volta ao Gemini na próxima chamada)."""
    global _modelo
    _modelo = modelo


def obter_embeddings() -> Embeddings:
    global _modelo
    if _modelo is None:
        _modelo = criar_embeddings_gemini()
    return _modelo


def _classificar_por_tipo(erro: BaseException) -> str | None:
    import httpx
    from google.genai import errors as genai_errors

    try:
        import httpx2  # alternativa ao httpx suportada pelo SDK
    except ImportError:
        httpx2 = None

    if isinstance(erro, genai_errors.APIError):
        codigo = erro.code
        if codigo == 429:
            return _LIMITE_DE_TAXA
        if codigo == 408:
            return _TIMEOUT
        if codigo in _CODIGOS_CONFIGURACAO:
            return _CONFIGURACAO
        if isinstance(codigo, int) and codigo >= 500:
            return _INDISPONIVEL
        return None
    if isinstance(erro, (httpx.TimeoutException, TimeoutError)):
        return _TIMEOUT
    if httpx2 is not None and isinstance(erro, httpx2.TimeoutException):
        return _TIMEOUT
    if isinstance(erro, (httpx.TransportError, ConnectionError)):
        return _INDISPONIVEL
    if httpx2 is not None and isinstance(erro, httpx2.TransportError):
        return _INDISPONIVEL
    return None


def _cadeia(erro: BaseException):
    """Percorre a exceção e as que a causaram (__cause__, depois __context__)."""
    vistos: set[int] = set()
    atual: BaseException | None = erro
    while atual is not None and id(atual) not in vistos:
        vistos.add(id(atual))
        yield atual
        atual = atual.__cause__ or atual.__context__


def _classificar(erro: BaseException) -> str | None:
    """Categoria do erro, ou None se não for falha do serviço de embeddings.

    Vale a primeira exceção reconhecida na cadeia (a própria, depois as que
    a causaram). O texto "429"/"RESOURCE_EXHAUSTED" fica como último recurso.
    """
    for item in _cadeia(erro):
        categoria = _classificar_por_tipo(item)
        if categoria is not None:
            return categoria
    texto = str(erro)
    if "429" in texto or "RESOURCE_EXHAUSTED" in texto:
        return _LIMITE_DE_TAXA
    return None


def _resumo(erro: BaseException) -> str:
    """Tipos e códigos da cadeia, para log (sem mensagens, chave ou texto do documento)."""
    partes = []
    for item in _cadeia(erro):
        codigo = getattr(item, "code", None)
        partes.append(f"{type(item).__name__}({codigo})" if codigo else type(item).__name__)
    return " <- ".join(partes)


def _fator_jitter() -> float:
    return random.uniform(1 - config.EMBEDDING_JITTER, 1 + config.EMBEDDING_JITTER)


def _com_retentativa(funcao, *args, **kwargs):
    espera = config.EMBEDDING_ESPERA_INICIAL
    for tentativa in range(1, config.EMBEDDING_TENTATIVAS + 1):
        try:
            return funcao(*args, **kwargs)
        except Exception as erro:
            categoria = _classificar(erro)
            if categoria is None:
                raise
            logger.warning(
                "Falha no serviço de embeddings (%s, tentativa %d de %d): %s",
                categoria,
                tentativa,
                config.EMBEDDING_TENTATIVAS,
                _resumo(erro),
            )
            if categoria == _CONFIGURACAO or tentativa == config.EMBEDDING_TENTATIVAS:
                raise RuntimeError(_MENSAGENS[categoria]) from erro
            time.sleep(espera * _fator_jitter())
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
