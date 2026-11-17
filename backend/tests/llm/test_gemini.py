"""Adaptador Gemini com cliente ``google.genai`` falso (sem rede)."""

from __future__ import annotations

import google.genai
import httpx
import pytest
from google.genai import errors as genai_errors

from app.llm import (
    ErroConfiguracao,
    ErroIndisponivel,
    ErroLimiteTaxa,
    ErroLLM,
    ErroRespostaInvalida,
    ErroTimeout,
    Mensagem,
)
from app.llm.gemini import ProvedorGemini

TEXTO_CRU = "detalhe-interno-do-sdk-123"
CHAVE_FALSA = "chave-falsa-so-para-teste"


class _Resposta:
    def __init__(self, texto):
        self._texto = texto

    @property
    def text(self):
        if isinstance(self._texto, BaseException):
            raise self._texto
        return self._texto


class _ClienteFalso:
    """Substitui ``google.genai.Client``; o roteiro diz o que cada chamada devolve."""

    criados: list[dict] = []
    chamadas: list[dict] = []
    roteiro: list = []

    def __init__(self, api_key=None, **_kwargs):
        _ClienteFalso.criados.append({"api_key": api_key})
        self.models = self

    def generate_content(self, *, model, contents, config=None):
        _ClienteFalso.chamadas.append({"model": model, "contents": contents, "config": config})
        item = _ClienteFalso.roteiro.pop(0) if _ClienteFalso.roteiro else "resposta"
        if isinstance(item, BaseException) and not isinstance(item, ValueError):
            raise item
        return _Resposta(item)


@pytest.fixture
def cliente(monkeypatch):
    _ClienteFalso.criados = []
    _ClienteFalso.chamadas = []
    _ClienteFalso.roteiro = []
    monkeypatch.setattr(google.genai, "Client", _ClienteFalso)
    monkeypatch.setenv("GOOGLE_API_KEY", CHAVE_FALSA)
    return _ClienteFalso


def _erro_api(codigo: int) -> genai_errors.APIError:
    corpo = {"error": {"code": codigo, "message": TEXTO_CRU, "status": "X"}}
    classe = genai_errors.ServerError if codigo >= 500 else genai_errors.ClientError
    return classe(codigo, corpo)


def _gerar(provedor, texto="oi", timeout=30):
    return provedor.gerar([Mensagem("user", texto)], timeout_segundos=timeout)


@pytest.mark.parametrize(
    "excecao,categoria",
    [
        (_erro_api(429), ErroLimiteTaxa),
        (_erro_api(408), ErroTimeout),
        (_erro_api(504), ErroTimeout),
        (_erro_api(400), ErroConfiguracao),
        (_erro_api(401), ErroConfiguracao),
        (_erro_api(403), ErroConfiguracao),
        (_erro_api(404), ErroConfiguracao),
        (_erro_api(500), ErroIndisponivel),
        (_erro_api(503), ErroIndisponivel),
        (_erro_api(409), ErroIndisponivel),
        (httpx.ReadTimeout(TEXTO_CRU), ErroTimeout),
        (TimeoutError(TEXTO_CRU), ErroTimeout),
        (httpx.ConnectError(TEXTO_CRU), ErroIndisponivel),
        (ConnectionError(TEXTO_CRU), ErroIndisponivel),
        (RuntimeError(TEXTO_CRU), ErroLLM),
    ],
    ids=[
        "429", "408", "504", "400", "401", "403", "404", "500", "503", "409-outro",
        "httpx-timeout", "timeout-python", "httpx-conexao", "conexao-python", "desconhecido",
    ],
)
def test_mapeia_excecoes_do_sdk(cliente, excecao, categoria):
    cliente.roteiro = [excecao]
    with pytest.raises(ErroLLM) as erro:
        _gerar(ProvedorGemini("modelo-x"))
    assert type(erro.value) is categoria
    assert TEXTO_CRU not in str(erro.value)
    assert erro.value.__cause__ is None  # nenhuma exceção do SDK vaza encadeada


def test_classifica_pela_causa_embrulhada(cliente):
    try:
        try:
            raise _erro_api(429)
        except genai_errors.APIError as causa:
            raise RuntimeError("embrulho") from causa
    except RuntimeError as embrulho:
        cliente.roteiro = [embrulho]
    with pytest.raises(ErroLimiteTaxa):
        _gerar(ProvedorGemini("modelo-x"))


@pytest.mark.parametrize(
    "texto", [None, "", "   \n", ValueError(f"sem candidatos {TEXTO_CRU}")],
    ids=["none", "vazio", "so-espacos", "acesso-ao-texto-falha"],
)
def test_resposta_sem_texto_vira_resposta_invalida(cliente, texto):
    cliente.roteiro = [texto]
    with pytest.raises(ErroRespostaInvalida) as erro:
        _gerar(ProvedorGemini("modelo-x"))
    assert TEXTO_CRU not in str(erro.value)


def test_mensagens_e_timeout_chegam_ao_sdk(cliente):
    provedor = ProvedorGemini("gemini-teste")
    texto = provedor.gerar(
        [
            Mensagem("system", "Você é um professor."),
            Mensagem("user", "Explique HTTP."),
            Mensagem("assistant", "HTTP é um protocolo."),
            Mensagem("user", "E o 404?"),
        ],
        timeout_segundos=12,
    )
    assert texto == "resposta"
    chamada = cliente.chamadas[0]
    assert chamada["model"] == "gemini-teste"
    assert chamada["config"].system_instruction == "Você é um professor."
    assert [c.role for c in chamada["contents"]] == ["user", "model", "user"]
    assert [c.parts[0].text for c in chamada["contents"]] == [
        "Explique HTTP.", "HTTP é um protocolo.", "E o 404?",
    ]
    assert chamada["config"].http_options.timeout == 12_000
    assert chamada["config"].http_options.retry_options is None


def test_so_usuario_nao_envia_instrucao_de_sistema(cliente):
    _gerar(ProvedorGemini("modelo-x"), texto="prompt completo")
    chamada = cliente.chamadas[0]
    assert chamada["config"].system_instruction is None
    assert [(c.role, c.parts[0].text) for c in chamada["contents"]] == [("user", "prompt completo")]


def test_cliente_criado_uma_vez_em_duas_geracoes(cliente):
    provedor = ProvedorGemini("modelo-x")
    assert cliente.criados == []  # criação preguiçosa
    _gerar(provedor)
    _gerar(provedor)
    assert len(cliente.criados) == 1
    assert cliente.criados[0]["api_key"] == CHAVE_FALSA
    assert len(cliente.chamadas) == 2


def test_sem_chave_falha_na_geracao_com_erro_de_configuracao(cliente, monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY")
    provedor = ProvedorGemini("modelo-x")
    with pytest.raises(ErroConfiguracao):
        _gerar(provedor)
    assert cliente.criados == []


def test_falha_ao_criar_cliente_vira_erro_de_configuracao(cliente, monkeypatch):
    def recusa(**_kwargs):
        raise ValueError(f"No API key {TEXTO_CRU}")

    monkeypatch.setattr(google.genai, "Client", recusa)
    with pytest.raises(ErroConfiguracao) as erro:
        _gerar(ProvedorGemini("modelo-x"))
    assert TEXTO_CRU not in str(erro.value)
    assert erro.value.__cause__ is None
