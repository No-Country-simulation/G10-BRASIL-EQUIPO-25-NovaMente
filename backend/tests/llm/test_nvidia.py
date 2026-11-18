"""Adaptador NVIDIA NIM com transporte HTTP simulado (``httpx.MockTransport``, sem rede)."""

from __future__ import annotations

import json
import logging

import httpx
import pytest
from pydantic import SecretStr

from app.core.config import settings
from app.llm import (
    ErroAutenticacao,
    ErroConfiguracao,
    ErroIndisponivel,
    ErroLimiteTaxa,
    ErroModeloIndisponivel,
    ErroRequisicaoRecusada,
    ErroRespostaInvalida,
    ErroTimeout,
    ErroTransitorio,
    Mensagem,
)
from app.llm.nvidia import ProvedorNvidia, criar_provedor_nvidia, remover_raciocinio

CHAVE_FALSA = "nvapi-chave-falsa-so-para-teste"
TEXTO_CRU = "detalhe-interno-do-servidor-123"
BASE = "https://nim.exemplo.test/v1"


def _resposta_ok(conteudo="resposta", **extra):
    mensagem = {"role": "assistant", "content": conteudo, **extra}
    return {"choices": [{"index": 0, "message": mensagem}], "usage": {"total_tokens": 42}}


class _Servidor:
    """Roteiro de respostas; cada item é dict (JSON 200), (status, corpo) ou exceção."""

    def __init__(self):
        self.roteiro: list = []
        self.requisicoes: list[httpx.Request] = []

    def __call__(self, requisicao: httpx.Request) -> httpx.Response:
        self.requisicoes.append(requisicao)
        item = self.roteiro.pop(0) if self.roteiro else _resposta_ok()
        if isinstance(item, BaseException):
            raise item
        if isinstance(item, tuple):
            status, corpo = item
            return httpx.Response(status, text=corpo)
        return httpx.Response(200, json=item)

    def corpo(self, indice: int = -1) -> dict:
        return json.loads(self.requisicoes[indice].content)


@pytest.fixture
def servidor(monkeypatch):
    monkeypatch.setattr(settings, "nvidia_nim_api_key", SecretStr(CHAVE_FALSA))
    return _Servidor()


@pytest.fixture
def provedor(servidor):
    return ProvedorNvidia(
        "nvidia/modelo-teste", BASE + "/", max_tokens=4096, transporte=httpx.MockTransport(servidor)
    )


def _gerar(provedor, texto="oi", timeout=30):
    return provedor.gerar([Mensagem("user", texto)], timeout_segundos=timeout)


# ── Sucesso e requisição ─────────────────────────────────────────────────────


def test_sucesso_monta_a_requisicao_openai(provedor, servidor):
    assert _gerar(provedor, "Explique HTTP.") == "resposta"
    (requisicao,) = servidor.requisicoes
    assert requisicao.method == "POST"
    assert str(requisicao.url) == f"{BASE}/chat/completions"
    assert requisicao.headers["Authorization"] == f"Bearer {CHAVE_FALSA}"
    corpo = servidor.corpo()
    assert corpo["model"] == "nvidia/modelo-teste"
    assert corpo["max_tokens"] == 4096
    assert corpo["stream"] is False
    assert "temperature" not in corpo  # sem temperatura configurada, vale o padrão do modelo
    assert provedor.ultimo_uso == {"total_tokens": 42}


def test_mapeia_os_papeis_juntando_o_sistema_no_inicio(provedor, servidor):
    provedor.gerar(
        [
            Mensagem("user", "Explique HTTP."),
            Mensagem("system", "Você é um professor."),
            Mensagem("assistant", "HTTP é um protocolo."),
            Mensagem("system", "Responda em português."),
            Mensagem("user", "E o 404?"),
        ],
        timeout_segundos=10,
    )
    assert servidor.corpo()["messages"] == [
        {"role": "system", "content": "Você é um professor.\n\nResponda em português."},
        {"role": "user", "content": "Explique HTTP."},
        {"role": "assistant", "content": "HTTP é um protocolo."},
        {"role": "user", "content": "E o 404?"},
    ]


def test_sem_mensagem_de_sistema_nao_cria_uma(provedor, servidor):
    _gerar(provedor)
    assert servidor.corpo()["messages"] == [{"role": "user", "content": "oi"}]


def test_temperatura_configurada_vai_na_requisicao(servidor):
    provedor = ProvedorNvidia("m", BASE, temperatura=0.2, transporte=httpx.MockTransport(servidor))
    _gerar(provedor)
    assert servidor.corpo()["temperature"] == 0.2
    assert "max_tokens" not in servidor.corpo()


def test_respeita_o_timeout_da_chamada(provedor, servidor):
    _gerar(provedor, timeout=12.5)
    tempos = servidor.requisicoes[0].extensions["timeout"]
    assert set(tempos.values()) == {12.5}


def test_reaproveita_o_cliente_http(provedor, servidor):
    _gerar(provedor)
    cliente = provedor._cliente
    _gerar(provedor)
    assert provedor._cliente is cliente
    assert len(servidor.requisicoes) == 2


# ── Raciocínio ────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "conteudo,esperado",
    [
        ('<think>vou montar o JSON</think>\n{"a": 1}', '{"a": 1}'),
        ('<THINK>\nlinha 1\nlinha 2\n</THINK>{"a": 1}', '{"a": 1}'),
        ('<think>um</think>{"a": <think>dois</think>1}', '{"a": 1}'),
        ('raciocínio sem abertura</think>\n{"a": 1}', '{"a": 1}'),
        ('{"a": 1}', '{"a": 1}'),
    ],
)
def test_remove_blocos_de_raciocinio(conteudo, esperado):
    assert remover_raciocinio(conteudo) == esperado


def test_usa_so_o_content_e_ignora_reasoning_content(provedor, servidor):
    servidor.roteiro = [_resposta_ok("<think>x</think>texto final", reasoning_content="pensando...")]
    assert _gerar(provedor) == "texto final"


# ── Erros ─────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "item,categoria",
    [
        ((429, TEXTO_CRU), ErroLimiteTaxa),
        ((500, TEXTO_CRU), ErroIndisponivel),
        ((502, TEXTO_CRU), ErroIndisponivel),
        ((503, TEXTO_CRU), ErroIndisponivel),
        ((504, TEXTO_CRU), ErroTimeout),
        ((408, TEXTO_CRU), ErroTimeout),
        (httpx.ReadTimeout(TEXTO_CRU), ErroTimeout),
        (httpx.ConnectTimeout(TEXTO_CRU), ErroTimeout),
        (httpx.ConnectError(TEXTO_CRU), ErroIndisponivel),
        (httpx.RemoteProtocolError(TEXTO_CRU), ErroIndisponivel),
    ],
    ids=["429", "500", "502", "503", "504", "408", "read-timeout", "connect-timeout",
         "conexao", "protocolo"],
)
def test_falhas_passageiras_sao_retentaveis(provedor, servidor, item, categoria):
    servidor.roteiro = [item]
    with pytest.raises(categoria) as erro:
        _gerar(provedor)
    assert isinstance(erro.value, (ErroTransitorio, ErroTimeout))  # o que a retentativa repete
    assert TEXTO_CRU not in str(erro.value)


@pytest.mark.parametrize(
    "status,categoria,trecho",
    [
        (401, ErroAutenticacao, "chave inválida ou sem acesso"),
        (403, ErroAutenticacao, "chave inválida ou sem acesso"),
        (404, ErroModeloIndisponivel, "modelo indisponível no catálogo"),
        (410, ErroModeloIndisponivel, "modelo removido do catálogo"),
        (400, ErroRequisicaoRecusada, "requisição recusada"),
        (409, ErroRequisicaoRecusada, "requisição recusada"),
        (422, ErroRequisicaoRecusada, "requisição recusada"),
    ],
)
def test_falhas_permanentes(provedor, servidor, status, categoria, trecho):
    servidor.roteiro = [(status, TEXTO_CRU)]
    with pytest.raises(categoria) as erro:
        _gerar(provedor)
    assert isinstance(erro.value, ErroConfiguracao)  # quem captura ErroConfiguracao continua pegando
    assert not isinstance(erro.value, (ErroTransitorio, ErroTimeout))
    assert trecho in str(erro.value)
    assert f"HTTP {status}" in str(erro.value)
    assert TEXTO_CRU not in str(erro.value)


@pytest.mark.parametrize(
    "item",
    [
        {"choices": []},
        {"id": "x"},
        {"choices": [{"message": {"role": "assistant", "content": None}}]},
        {"choices": [{"message": {"role": "assistant"}}]},
        _resposta_ok(""),
        _resposta_ok("   \n"),
        _resposta_ok("<think>só raciocínio</think>"),
        (200, "isto não é json"),
        ["lista", "em vez de objeto"],
    ],
    ids=["choices-vazio", "sem-choices", "content-null", "sem-content", "vazio", "espacos",
         "so-raciocinio", "nao-json", "lista"],
)
def test_resposta_sem_conteudo_e_invalida(provedor, servidor, item):
    servidor.roteiro = [item]
    with pytest.raises(ErroRespostaInvalida):
        _gerar(provedor)


def test_chave_ausente_e_erro_de_configuracao_sem_chamar_a_api(servidor, monkeypatch):
    monkeypatch.setattr(settings, "nvidia_nim_api_key", SecretStr(""))
    provedor = ProvedorNvidia("m", BASE, transporte=httpx.MockTransport(servidor))
    with pytest.raises(ErroConfiguracao, match="NVIDIA_NIM_API_KEY não definida"):
        _gerar(provedor)
    assert servidor.requisicoes == []


# ── A chave nunca aparece ─────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "item",
    [
        (401, f"chave recusada: {CHAVE_FALSA}"),
        (500, f"Authorization: Bearer {CHAVE_FALSA}"),
        httpx.ConnectError(f"falhou com Bearer {CHAVE_FALSA}"),
        httpx.ReadTimeout(CHAVE_FALSA),
        (200, CHAVE_FALSA),
        {"choices": []},
    ],
    ids=["401-ecoa-chave", "500-ecoa-cabecalho", "conexao", "timeout", "nao-json", "sem-choices"],
)
def test_chave_nao_aparece_em_erro_repr_nem_log(provedor, servidor, item, caplog):
    servidor.roteiro = [item]
    with caplog.at_level(logging.DEBUG):
        with pytest.raises(Exception) as erro:
            _gerar(provedor)
    textos = [str(erro.value), repr(erro.value), repr(provedor), caplog.text]
    textos += [str(e) for e in (erro.value.__cause__, erro.value.__context__) if e and not erro.value.__suppress_context__]
    assert all(CHAVE_FALSA not in texto for texto in textos)
    assert all("Bearer" not in texto for texto in textos)
    assert erro.value.__cause__ is None


def test_chave_nao_aparece_no_repr_das_configuracoes(monkeypatch):
    monkeypatch.setattr(settings, "nvidia_nim_api_key", SecretStr(CHAVE_FALSA))
    assert CHAVE_FALSA not in repr(settings)
    assert CHAVE_FALSA not in str(settings.model_dump())


# ── Catálogo de modelos ───────────────────────────────────────────────────────


def test_modelo_disponivel_consulta_o_catalogo(provedor, servidor):
    servidor.roteiro = [{"object": "list", "data": [{"id": "outro/modelo"}, {"id": "nvidia/modelo-teste"}]}]
    assert provedor.modelo_disponivel() is True
    (requisicao,) = servidor.requisicoes
    assert requisicao.method == "GET"
    assert str(requisicao.url) == f"{BASE}/models"


def test_modelo_fora_do_catalogo(provedor, servidor):
    servidor.roteiro = [{"data": [{"id": "outro/modelo"}, "lixo", {"sem": "id"}]}]
    assert provedor.modelo_disponivel() is False


@pytest.mark.parametrize(
    "item,categoria",
    [((401, ""), ErroConfiguracao), ({"modelos": []}, ErroRespostaInvalida), ((503, ""), ErroIndisponivel)],
)
def test_catalogo_com_erro(provedor, servidor, item, categoria):
    servidor.roteiro = [item]
    with pytest.raises(categoria):
        provedor.modelo_disponivel()


# ── Configuração ──────────────────────────────────────────────────────────────


def test_criar_provedor_usa_as_configuracoes(monkeypatch):
    monkeypatch.setattr(settings, "nvidia_nim_modelo", "org/modelo-configurado")
    monkeypatch.setattr(settings, "nvidia_nim_base_url", BASE)
    monkeypatch.setattr(settings, "nvidia_nim_temperatura", 0.3)
    monkeypatch.setattr(settings, "nvidia_nim_max_tokens", 2048)
    provedor = criar_provedor_nvidia()
    assert (provedor.modelo, provedor.base_url, provedor.temperatura, provedor.max_tokens) == (
        "org/modelo-configurado", BASE, 0.3, 2048,
    )
    assert criar_provedor_nvidia("org/outro").modelo == "org/outro"


def test_configuracoes_padrao(monkeypatch):
    from app.core.config import Settings

    for variavel in ("NVIDIA_NIM_API_KEY", "NVIDIA_NIM_BASE_URL", "NVIDIA_NIM_MODELO",
                     "NVIDIA_NIM_TEMPERATURA", "NVIDIA_NIM_MAX_TOKENS", "NVIDIA_NIM_RACIOCINIO",
                     "NVIDIA_NIM_ORCAMENTO_RACIOCINIO"):
        monkeypatch.delenv(variavel, raising=False)
    config = Settings(_env_file=None)
    assert config.nvidia_nim_api_key.get_secret_value() == ""
    assert config.nvidia_nim_base_url == "https://integrate.api.nvidia.com/v1"
    assert config.nvidia_nim_modelo
    assert config.nvidia_nim_temperatura is None
    assert config.nvidia_nim_max_tokens == 8192
    assert config.nvidia_nim_raciocinio == ""
    assert config.nvidia_nim_orcamento_raciocinio is None


def test_configuracoes_vem_do_ambiente(monkeypatch):
    from app.core.config import Settings

    monkeypatch.setenv("NVIDIA_NIM_API_KEY", CHAVE_FALSA)
    monkeypatch.setenv("NVIDIA_NIM_MODELO", "org/modelo-env")
    monkeypatch.setenv("NVIDIA_NIM_TEMPERATURA", "0.1")
    config = Settings(_env_file=None)
    assert config.nvidia_nim_api_key.get_secret_value() == CHAVE_FALSA
    assert config.nvidia_nim_modelo == "org/modelo-env"
    assert config.nvidia_nim_temperatura == 0.1


# ── Raciocínio ligado/desligado e orçamento ──────────────────────────────────


def _provedor_com(servidor, **opcoes):
    return ProvedorNvidia("m", BASE, transporte=httpx.MockTransport(servidor), **opcoes)


@pytest.mark.parametrize(
    "raciocinio,orcamento,esperado",
    [
        ("", None, {}),
        ("", 2048, {"reasoning_budget": 2048}),
        ("ligado", None, {"chat_template_kwargs": {"enable_thinking": True}}),
        ("ligado", 16384, {"chat_template_kwargs": {"enable_thinking": True}, "reasoning_budget": 16384}),
        ("desligado", None, {"chat_template_kwargs": {"enable_thinking": False}}),
        ("desligado", 16384, {"chat_template_kwargs": {"enable_thinking": False}}),  # orçamento não faz sentido
    ],
)
def test_parametros_de_raciocinio_no_nivel_raiz(servidor, raciocinio, orcamento, esperado):
    _gerar(_provedor_com(servidor, raciocinio=raciocinio, orcamento_raciocinio=orcamento))
    corpo = servidor.corpo()
    extras = {chave: corpo[chave] for chave in ("chat_template_kwargs", "reasoning_budget") if chave in corpo}
    assert extras == esperado
    assert {"model", "messages", "stream"} <= set(corpo)  # ao lado de model e messages, sem extra_body
    assert "extra_body" not in corpo


def test_raciocinio_invalido_no_provedor():
    with pytest.raises(ValueError, match="ligado, desligado"):
        ProvedorNvidia("m", BASE, raciocinio="talvez")


def test_criar_provedor_usa_o_raciocinio_da_configuracao_e_aceita_substituir(monkeypatch):
    monkeypatch.setattr(settings, "nvidia_nim_raciocinio", "ligado")
    monkeypatch.setattr(settings, "nvidia_nim_orcamento_raciocinio", 4096)
    padrao = criar_provedor_nvidia()
    assert (padrao.raciocinio, padrao.orcamento_raciocinio) == ("ligado", 4096)
    substituido = criar_provedor_nvidia("org/m", raciocinio="", orcamento_raciocinio=None)
    assert (substituido.raciocinio, substituido.orcamento_raciocinio) == ("", None)
    assert criar_provedor_nvidia(raciocinio="desligado").orcamento_raciocinio == 4096


# ── Resposta cortada (finish_reason "length") ─────────────────────────────────


@pytest.mark.parametrize("conteudo", ['{"titulo": "cortado no mei', "", None])
def test_resposta_cortada_e_invalida_mesmo_com_texto(provedor, servidor, conteudo):
    resposta = _resposta_ok(conteudo)
    resposta["choices"][0]["finish_reason"] = "length"
    servidor.roteiro = [resposta]
    with pytest.raises(ErroRespostaInvalida, match="cortada pelo limite de tokens; aumente NVIDIA_NIM_MAX_TOKENS"):
        _gerar(provedor)
    assert provedor.ultimo_motivo_fim == "length"
    assert provedor.ultimo_uso == {"total_tokens": 42}


def test_guarda_o_motivo_de_fim(provedor, servidor):
    resposta = _resposta_ok("ok")
    resposta["choices"][0]["finish_reason"] = "stop"
    servidor.roteiro = [resposta, _resposta_ok("sem motivo")]
    _gerar(provedor)
    assert provedor.ultimo_motivo_fim == "stop"
    _gerar(provedor)
    assert provedor.ultimo_motivo_fim is None  # não fica o da chamada anterior


# ── listar_modelos ────────────────────────────────────────────────────────────


def test_listar_modelos_em_ordem_sem_repeticao(provedor, servidor):
    servidor.roteiro = [{"data": [{"id": "z/b"}, {"id": "a/c"}, "lixo", {"sem": "id"}, {"id": 7}, {"id": "a/c"}]}]
    assert provedor.listar_modelos() == ["a/c", "z/b"]
    assert servidor.requisicoes[0].method == "GET"
    assert str(servidor.requisicoes[0].url) == f"{BASE}/models"


@pytest.mark.parametrize("item", [{"modelos": []}, {"data": "x"}, ["lista"]], ids=["sem-data", "data-texto", "lista"])
def test_listar_modelos_com_formato_inesperado(provedor, servidor, item):
    servidor.roteiro = [item]
    with pytest.raises(ErroRespostaInvalida, match="formato inesperado"):
        provedor.listar_modelos()


def test_listar_modelos_com_chave_recusada(provedor, servidor):
    servidor.roteiro = [(401, "")]
    with pytest.raises(ErroAutenticacao):
        provedor.listar_modelos()


# ── Configuração: valores vazios e raciocínio ─────────────────────────────────


def test_valores_vazios_no_ambiente_viram_none(monkeypatch):
    from app.core.config import Settings

    monkeypatch.setenv("NVIDIA_NIM_TEMPERATURA", "")
    monkeypatch.setenv("NVIDIA_NIM_ORCAMENTO_RACIOCINIO", "  ")
    monkeypatch.setenv("NVIDIA_NIM_RACIOCINIO", "")
    config = Settings(_env_file=None)
    assert config.nvidia_nim_temperatura is None
    assert config.nvidia_nim_orcamento_raciocinio is None
    assert config.nvidia_nim_raciocinio == ""


def test_valores_vazios_no_arquivo_env_nao_quebram(tmp_path):
    from app.core.config import Settings

    arquivo = tmp_path / "exemplo.env"
    arquivo.write_text(
        "NVIDIA_NIM_TEMPERATURA=\nNVIDIA_NIM_ORCAMENTO_RACIOCINIO=\nNVIDIA_NIM_RACIOCINIO=\n", encoding="utf-8"
    )
    config = Settings(_env_file=arquivo)
    assert (config.nvidia_nim_temperatura, config.nvidia_nim_orcamento_raciocinio) == (None, None)


@pytest.mark.parametrize("valor,esperado", [("ligado", "ligado"), (" DESLIGADO ", "desligado")])
def test_raciocinio_aceito(monkeypatch, valor, esperado):
    from app.core.config import Settings

    monkeypatch.setenv("NVIDIA_NIM_RACIOCINIO", valor)
    monkeypatch.setenv("NVIDIA_NIM_ORCAMENTO_RACIOCINIO", "16384")
    config = Settings(_env_file=None)
    assert config.nvidia_nim_raciocinio == esperado
    assert config.nvidia_nim_orcamento_raciocinio == 16384


@pytest.mark.parametrize("variavel,valor,trecho", [
    ("NVIDIA_NIM_RACIOCINIO", "talvez", "Valores válidos: vazio (padrão do modelo), ligado, desligado"),
    ("NVIDIA_NIM_ORCAMENTO_RACIOCINIO", "0", "greater than or equal to 1"),
    ("NVIDIA_NIM_ORCAMENTO_RACIOCINIO", "muito", "integer"),
])
def test_valor_invalido_impede_a_subida(monkeypatch, variavel, valor, trecho):
    from pydantic import ValidationError

    from app.core.config import Settings

    monkeypatch.setenv(variavel, valor)
    with pytest.raises(ValidationError, match=trecho.replace("(", r"\(").replace(")", r"\)")):
        Settings(_env_file=None)
