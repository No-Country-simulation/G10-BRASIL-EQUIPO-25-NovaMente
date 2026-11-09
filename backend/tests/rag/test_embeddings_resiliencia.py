"""Timeout, classificação de erros e retentativa dos embeddings (sem rede)."""

import httpx
import pytest
import google.genai
from google.genai import errors as genai_errors
from langchain_core.embeddings import Embeddings

from app.rag import config, embeddings

TEXTO_CRU = "detalhe-interno-do-sdk-123"

MSG_TIMEOUT = "O serviço de embeddings demorou demais para responder. Tente novamente."
MSG_LIMITE = (
    "O limite de uso do serviço de embeddings foi atingido. "
    "Tente novamente em alguns minutos."
)
MSG_INDISPONIVEL = (
    "O serviço de embeddings está indisponível no momento. Tente novamente em instantes."
)
MSG_CONFIGURACAO = (
    "O serviço de embeddings não está configurado corretamente "
    "(modelo ou chave de API). Avise a equipe."
)


def _erro_api(codigo: int, status: str) -> genai_errors.APIError:
    corpo = {"error": {"code": codigo, "message": TEXTO_CRU, "status": status}}
    classe = genai_errors.ServerError if codigo >= 500 else genai_errors.ClientError
    return classe(codigo, corpo)


def _embrulhado(original: BaseException) -> Exception:
    """Exceção genérica que tem a original como causa (testa a cadeia)."""
    try:
        raise original
    except BaseException as causa:
        try:
            raise Exception("falha ao gerar embeddings") from causa
        except Exception as embrulho:
            return embrulho


def _limite():
    return _erro_api(429, "RESOURCE_EXHAUSTED")


def _indisponivel():
    return _erro_api(503, "UNAVAILABLE")


def _timeout():
    return httpx.ReadTimeout(TEXTO_CRU)


def _conexao():
    return httpx.ConnectError(TEXTO_CRU)


class _EmbeddingRoteirizado(Embeddings):
    """Falha conforme o roteiro (lista de exceções ou None) e depois responde."""

    def __init__(self, roteiro):
        self.roteiro = list(roteiro)
        self.chamadas: list[tuple[str, int]] = []

    def _proximo(self):
        if self.roteiro:
            erro = self.roteiro.pop(0)
            if erro is not None:
                raise erro

    def embed_documents(self, texts, task_type=None, **_):
        self.chamadas.append(("documentos", len(texts)))
        self._proximo()
        return [[float(len(t)), 1.0] for t in texts]

    def embed_query(self, text, task_type=None, **_):
        self.chamadas.append(("consulta", 1))
        self._proximo()
        return [float(len(text)), 1.0]


@pytest.fixture
def esperas(monkeypatch):
    registradas: list[float] = []
    monkeypatch.setattr(embeddings.time, "sleep", registradas.append)
    monkeypatch.setattr(embeddings, "_fator_jitter", lambda: 1.0)
    return registradas


@pytest.fixture
def roteiro():
    def instalar(*erros):
        falso = _EmbeddingRoteirizado(erros)
        embeddings.definir_embeddings(falso)
        return falso

    yield instalar
    embeddings.definir_embeddings(None)


# ── Cliente Gemini (com google.genai.Client falso, sem rede) ─────────────────


class _Valores:
    def __init__(self, valores):
        self.values = valores


class _RespostaEmbed:
    def __init__(self, quantidade):
        self.embeddings = [_Valores([float(i), 0.5]) for i in range(quantidade)]


class _ClienteFalso:
    criados: list[dict] = []
    chamadas: list[dict] = []

    def __init__(self, api_key=None, http_options=None):
        _ClienteFalso.criados.append({"api_key": api_key, "http_options": http_options})
        self.models = self

    def embed_content(self, *, model, contents, config=None):
        _ClienteFalso.chamadas.append({"model": model, "contents": contents, "config": config})
        return _RespostaEmbed(len(contents))


@pytest.fixture
def cliente_falso(monkeypatch):
    _ClienteFalso.criados = []
    _ClienteFalso.chamadas = []
    monkeypatch.setattr(google.genai, "Client", _ClienteFalso)
    monkeypatch.setenv("GOOGLE_API_KEY", "chave-falsa-so-para-teste")
    return _ClienteFalso


def test_cliente_criado_com_timeout_em_ms_sem_retentativa(cliente_falso, monkeypatch):
    monkeypatch.setattr(config, "EMBEDDING_TIMEOUT_SEGUNDOS", 12)
    modelo = embeddings.criar_embeddings_gemini()
    assert isinstance(modelo, embeddings.EmbeddingsGemini)
    assert len(cliente_falso.criados) == 1
    opcoes = cliente_falso.criados[0]["http_options"]
    assert opcoes.timeout == 12_000
    assert opcoes.retry_options is None
    assert cliente_falso.criados[0]["api_key"] == "chave-falsa-so-para-teste"


def test_embed_documents_envia_modelo_conteudo_e_task_type(cliente_falso):
    modelo = embeddings.criar_embeddings_gemini()
    vetores = modelo.embed_documents(["um", "dois"], task_type=config.TASK_TYPE_DOCUMENTO)
    assert vetores == [[0.0, 0.5], [1.0, 0.5]]
    chamada = cliente_falso.chamadas[0]
    assert chamada["model"] == config.MODELO_EMBEDDING
    assert chamada["contents"] == [{"parts": [{"text": "um"}]}, {"parts": [{"text": "dois"}]}]
    assert chamada["config"].task_type == config.TASK_TYPE_DOCUMENTO


def test_embed_query_envia_task_type_de_consulta(cliente_falso):
    modelo = embeddings.criar_embeddings_gemini()
    assert modelo.embed_query("pergunta", task_type=config.TASK_TYPE_CONSULTA) == [0.0, 0.5]
    chamada = cliente_falso.chamadas[0]
    assert chamada["contents"] == [{"parts": [{"text": "pergunta"}]}]
    assert chamada["config"].task_type == config.TASK_TYPE_CONSULTA


def test_vetorizar_trechos_usa_o_cliente_gemini_em_lotes(cliente_falso, monkeypatch):
    monkeypatch.setattr(config, "EMBEDDING_LOTE", 2)
    embeddings.definir_embeddings(None)
    try:
        vetores = embeddings.vetorizar_trechos(["a", "b", "c"])
    finally:
        embeddings.definir_embeddings(None)
    assert len(vetores) == 3
    assert [len(c["contents"]) for c in cliente_falso.chamadas] == [2, 1]


def test_sem_chave_falha_com_value_error(cliente_falso, monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY")
    with pytest.raises(ValueError, match="GOOGLE_API_KEY"):
        embeddings.criar_embeddings_gemini()
    assert cliente_falso.criados == []


# ── Transitórios: retentados e recuperados ───────────────────────────────────


@pytest.mark.parametrize(
    "gerar", [_limite, _indisponivel, _timeout, _conexao],
    ids=["429", "503", "timeout", "conexao"],
)
def test_transitorio_retentado_e_recuperado(roteiro, esperas, gerar):
    falso = roteiro(gerar(), gerar())
    assert embeddings.vetorizar_trechos(["um", "dois"]) == [[2.0, 1.0], [4.0, 1.0]]
    assert len(falso.chamadas) == 3
    assert len(esperas) == 2


@pytest.mark.parametrize(
    "gerar,mensagem",
    [
        (_limite, MSG_LIMITE),
        (_indisponivel, MSG_INDISPONIVEL),
        (_timeout, MSG_TIMEOUT),
        (_conexao, MSG_INDISPONIVEL),
        (lambda: _erro_api(408, "DEADLINE_EXCEEDED"), MSG_TIMEOUT),
    ],
    ids=["429", "503", "timeout", "conexao", "408"],
)
def test_esgotamento_vira_runtime_error_sem_texto_cru(roteiro, esperas, gerar, mensagem):
    falso = roteiro(*[gerar() for _ in range(config.EMBEDDING_TENTATIVAS)])
    with pytest.raises(RuntimeError) as erro:
        embeddings.vetorizar_trechos(["um"])
    assert str(erro.value) == mensagem
    assert TEXTO_CRU not in str(erro.value)
    assert len(falso.chamadas) == config.EMBEDDING_TENTATIVAS


# ── Permanentes: falham na hora ───────────────────────────────────────────────


@pytest.mark.parametrize(
    "codigo,status",
    [(400, "INVALID_ARGUMENT"), (401, "UNAUTHENTICATED"), (403, "PERMISSION_DENIED"), (404, "NOT_FOUND")],
    ids=["400-argumento", "401-chave", "403-permissao", "404-modelo"],
)
def test_erro_permanente_falha_na_hora(roteiro, esperas, codigo, status):
    falso = roteiro(_erro_api(codigo, status))
    with pytest.raises(RuntimeError) as erro:
        embeddings.vetorizar_trechos(["um"])
    assert str(erro.value) == MSG_CONFIGURACAO
    assert TEXTO_CRU not in str(erro.value)
    assert len(falso.chamadas) == 1
    assert esperas == []


@pytest.mark.parametrize(
    "gerar,mensagem",
    [
        (lambda: _embrulhado(_erro_api(404, "NOT_FOUND")), MSG_CONFIGURACAO),
        (lambda: _embrulhado(httpx.ConnectTimeout(TEXTO_CRU)), MSG_TIMEOUT),
    ],
    ids=["404-na-causa", "timeout-na-causa"],
)
def test_classifica_pela_causa_quando_a_excecao_vem_embrulhada(roteiro, esperas, gerar, mensagem):
    roteiro(*[gerar() for _ in range(config.EMBEDDING_TENTATIVAS)])
    with pytest.raises(RuntimeError) as erro:
        embeddings.vetorizar_trechos(["um"])
    assert str(erro.value) == mensagem


def test_value_error_de_entrada_continua_value_error(roteiro, esperas):
    falso = roteiro(ValueError("entrada inválida"))
    with pytest.raises(ValueError, match="entrada inválida"):
        embeddings.vetorizar_trechos(["um"])
    assert len(falso.chamadas) == 1


# ── Espera exponencial e jitter ───────────────────────────────────────────────


def test_esperas_crescem_a_cada_tentativa(roteiro, esperas, monkeypatch):
    monkeypatch.setattr(config, "EMBEDDING_TENTATIVAS", 4)
    roteiro(_limite(), _limite(), _limite())
    embeddings.vetorizar_trechos(["um"])
    inicial = config.EMBEDDING_ESPERA_INICIAL
    assert esperas == [inicial, inicial * 2, inicial * 4]


def test_jitter_fica_na_faixa_configurada():
    for _ in range(200):
        fator = embeddings._fator_jitter()
        assert 1 - config.EMBEDDING_JITTER <= fator <= 1 + config.EMBEDDING_JITTER


# ── Consulta e lotes ──────────────────────────────────────────────────────────


def test_consulta_tem_a_mesma_protecao(roteiro, esperas):
    falso = roteiro(_timeout())
    assert embeddings.vetorizar_consulta("pergunta") == [8.0, 1.0]
    assert falso.chamadas == [("consulta", 1), ("consulta", 1)]

    falso = roteiro(_erro_api(401, "UNAUTHENTICATED"))
    with pytest.raises(RuntimeError, match="configurado corretamente"):
        embeddings.vetorizar_consulta("pergunta")
    assert len(falso.chamadas) == 1


def test_falha_num_lote_nao_refaz_os_anteriores(roteiro, esperas, monkeypatch):
    monkeypatch.setattr(config, "EMBEDDING_LOTE", 2)
    # 1º lote ok, 2º lote falha uma vez, 3º lote ok.
    falso = roteiro(None, _indisponivel(), None, None)
    vetores = embeddings.vetorizar_trechos(["a", "bb", "ccc", "dddd", "eeeee"])
    assert [v[0] for v in vetores] == [1.0, 2.0, 3.0, 4.0, 5.0]
    assert [c[1] for c in falso.chamadas] == [2, 2, 2, 1]  # só o 2º lote repetiu
