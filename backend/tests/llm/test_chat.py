"""Provedor do chat: configuração CHAT_*, fábrica com cache próprio, retentativa e prazo.

Nada acessa a rede: os provedores NVIDIA são só criados (sem gerar), e a
retentativa usa provedores falsos com relógio falso.
"""

from __future__ import annotations

import threading

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr, ValidationError

from app.core.config import Settings, settings
from app.llm import (
    ErroAutenticacao,
    ErroConfiguracao,
    ErroIndisponivel,
    ErroLimiteTaxa,
    ErroModeloIndisponivel,
    ErroRespostaInvalida,
    ErroTimeout,
    Mensagem,
    ModeloNaoPermitido,
    ProvedorDesconhecido,
    ProvedorDoChat,
    limites_da_geracao,
    modelos_do_chat,
    obter_provedor,
    obter_provedor_chat,
    validar_provedor_chat_configurado,
)
from app.llm.gemini import ProvedorGemini
from app.llm.nvidia import ProvedorNvidia
from app.llm.retentativa import _limites
from app.main import app

CHAVE_FALSA = "nvapi-chave-falsa-do-chat-123"
VARIAVEIS_CHAT = [
    "CHAT_LLM_PROVIDER", "CHAT_LLM_MODELO", "CHAT_LLM_RACIOCINIO", "CHAT_LLM_MAX_TOKENS",
    "CHAT_LLM_TEMPERATURA", "CHAT_LLM_TIMEOUT_SEGUNDOS", "CHAT_MODELOS_PERMITIDOS",
    "CHAT_MAX_PERGUNTA_CARACTERES", "CHAT_MAX_MENSAGENS_HISTORICO",
    "CHAT_MAX_CONTEXTO_CARACTERES", "CHAT_LIMITE_POR_MINUTO",
]
MENSAGENS = [Mensagem("system", "Responda só com base no material."), Mensagem("user", "O que é GET?")]


@pytest.fixture
def chat_padrao(monkeypatch):
    """Settings do chat nos padrões, com uma chave falsa para conferir que ela não vaza."""
    padrao = Settings(_env_file=None)
    for campo in Settings.model_fields:
        if campo.startswith("chat_"):
            monkeypatch.setattr(settings, campo, getattr(padrao, campo))
    monkeypatch.setattr(settings, "nvidia_nim_modelo", "nvidia/modelo-padrao")
    monkeypatch.setattr(settings, "nvidia_nim_api_key", SecretStr(CHAVE_FALSA))


# ── Configuração ──────────────────────────────────────────────────────────────


def _settings_com(monkeypatch, **variaveis) -> Settings:
    for nome in VARIAVEIS_CHAT:
        monkeypatch.delenv(nome, raising=False)
    for nome, valor in variaveis.items():
        monkeypatch.setenv(nome, valor)
    return Settings(_env_file=None)


def test_padroes_sem_nenhuma_variavel_chat(monkeypatch):
    s = _settings_com(monkeypatch)
    assert s.chat_llm_provider == "nvidia"
    assert s.chat_llm_modelo == ""
    assert s.chat_llm_raciocinio == "desligado"
    assert s.chat_llm_max_tokens == 1024
    assert s.chat_llm_temperatura == 0.2
    assert s.chat_llm_timeout_segundos == 45
    assert s.chat_modelos_permitidos == ""
    assert (
        s.chat_max_pergunta_caracteres,
        s.chat_max_mensagens_historico,
        s.chat_max_contexto_caracteres,
        s.chat_limite_por_minuto,
    ) == (1000, 10, 24_000, 12)


def test_variaveis_vazias_valem_o_padrao(monkeypatch):
    s = _settings_com(monkeypatch, **{nome: "" for nome in VARIAVEIS_CHAT})
    assert s.chat_llm_provider == "nvidia"
    assert s.chat_llm_raciocinio == "desligado"
    assert s.chat_llm_max_tokens == 1024
    assert s.chat_llm_temperatura == 0.2
    assert s.chat_llm_timeout_segundos == 45
    assert s.chat_limite_por_minuto == 12


def test_valores_sao_normalizados(monkeypatch):
    s = _settings_com(
        monkeypatch,
        CHAT_LLM_PROVIDER="  NVIDIA ",
        CHAT_LLM_RACIOCINIO=" Ligado ",
        CHAT_LLM_MODELO=" org/modelo ",
        CHAT_LLM_TEMPERATURA="0",
        CHAT_LLM_MAX_TOKENS="64",
    )
    assert (s.chat_llm_provider, s.chat_llm_raciocinio, s.chat_llm_modelo) == (
        "nvidia", "ligado", "org/modelo",
    )
    assert (s.chat_llm_temperatura, s.chat_llm_max_tokens) == (0, 64)


@pytest.mark.parametrize(
    "variavel,valor,trecho",
    [
        ("CHAT_LLM_RACIOCINIO", "talvez", "CHAT_LLM_RACIOCINIO 'talvez' inválido"),
        ("CHAT_LLM_MAX_TOKENS", "63", "chat_llm_max_tokens"),
        ("CHAT_LLM_TEMPERATURA", "2.5", "chat_llm_temperatura"),
        ("CHAT_LLM_TEMPERATURA", "-0.1", "chat_llm_temperatura"),
        ("CHAT_LLM_TIMEOUT_SEGUNDOS", "4", "chat_llm_timeout_segundos"),
        ("CHAT_MAX_PERGUNTA_CARACTERES", "0", "chat_max_pergunta_caracteres"),
        ("CHAT_MAX_MENSAGENS_HISTORICO", "0", "chat_max_mensagens_historico"),
        ("CHAT_MAX_CONTEXTO_CARACTERES", "-1", "chat_max_contexto_caracteres"),
        ("CHAT_LIMITE_POR_MINUTO", "0", "chat_limite_por_minuto"),
        ("CHAT_LLM_MAX_TOKENS", "muitos", "chat_llm_max_tokens"),
    ],
)
def test_valores_invalidos_falham_com_mensagem_clara(monkeypatch, variavel, valor, trecho):
    with pytest.raises(ValidationError) as erro:
        _settings_com(monkeypatch, **{variavel: valor})
    assert trecho in str(erro.value)


# ── Fábrica ───────────────────────────────────────────────────────────────────


def test_provedor_padrao_e_nvidia_com_os_parametros_do_chat(chat_padrao):
    provedor = obter_provedor_chat()
    assert isinstance(provedor, ProvedorDoChat)
    base = provedor.base
    assert isinstance(base, ProvedorNvidia)
    assert base.modelo == "nvidia/modelo-padrao"
    assert base.temperatura == 0.2
    assert base.max_tokens == 1024
    assert base.raciocinio == "desligado"
    assert base.orcamento_raciocinio is None
    assert base.base_url == settings.nvidia_nim_base_url.rstrip("/")


def test_chat_llm_modelo_e_parametros_configurados(chat_padrao, monkeypatch):
    monkeypatch.setattr(settings, "chat_llm_modelo", "google/gemma-4-31b-it")
    monkeypatch.setattr(settings, "chat_llm_temperatura", 0.7)
    monkeypatch.setattr(settings, "chat_llm_max_tokens", 2048)
    monkeypatch.setattr(settings, "chat_llm_raciocinio", "ligado")
    base = obter_provedor_chat().base
    assert (base.modelo, base.temperatura, base.max_tokens, base.raciocinio) == (
        "google/gemma-4-31b-it", 0.7, 2048, "ligado",
    )


def test_reaproveita_a_instancia_e_cria_outra_para_outro_modelo(chat_padrao, monkeypatch):
    monkeypatch.setattr(settings, "chat_modelos_permitidos", "org/outro")
    padrao = obter_provedor_chat()
    assert obter_provedor_chat() is padrao
    assert obter_provedor_chat("nvidia/modelo-padrao") is padrao
    assert obter_provedor_chat("  ") is padrao
    outro = obter_provedor_chat("org/outro")
    assert outro is not padrao
    assert outro.base.modelo == "org/outro"
    assert obter_provedor_chat("org/outro") is outro


def test_raciocinio_diferente_e_outra_instancia(chat_padrao, monkeypatch):
    desligado = obter_provedor_chat()
    monkeypatch.setattr(settings, "chat_llm_raciocinio", "ligado")
    ligado = obter_provedor_chat()
    assert ligado is not desligado
    assert ligado.base.raciocinio == "ligado"


def test_modelo_fora_da_lista_levanta_erro_especifico_sem_a_chave(chat_padrao, monkeypatch):
    monkeypatch.setattr(settings, "chat_modelos_permitidos", "org/a, org/b")
    with pytest.raises(ModeloNaoPermitido) as erro:
        obter_provedor_chat("org/c")
    assert isinstance(erro.value, ErroConfiguracao)
    mensagem = str(erro.value)
    assert "'org/c'" in mensagem
    assert "nvidia/modelo-padrao, org/a, org/b" in mensagem
    assert erro.value.permitidos == ["nvidia/modelo-padrao", "org/a", "org/b"]
    assert CHAVE_FALSA not in mensagem
    assert CHAVE_FALSA not in repr(erro.value)
    assert CHAVE_FALSA not in repr(obter_provedor_chat())


def test_lista_vazia_permite_so_o_modelo_padrao(chat_padrao):
    assert modelos_do_chat() == ["nvidia/modelo-padrao"]
    assert obter_provedor_chat("nvidia/modelo-padrao").base.modelo == "nvidia/modelo-padrao"
    with pytest.raises(ModeloNaoPermitido):
        obter_provedor_chat("org/qualquer")


def test_modelos_do_chat_padrao_primeiro_sem_repeticao(chat_padrao, monkeypatch):
    monkeypatch.setattr(settings, "chat_llm_modelo", "org/principal")
    monkeypatch.setattr(settings, "chat_modelos_permitidos", " org/b , org/a,, org/a, org/principal ,")
    assert modelos_do_chat() == ["org/principal", "org/b", "org/a"]


def test_provedor_do_chat_desconhecido(chat_padrao, monkeypatch):
    monkeypatch.setattr(settings, "chat_llm_provider", "inexistente")
    with pytest.raises(ProvedorDesconhecido, match="CHAT_LLM_PROVIDER 'inexistente' desconhecido") as erro:
        obter_provedor_chat()
    assert "nvidia" in str(erro.value)


def test_raciocinio_invalido_em_tempo_de_execucao(chat_padrao, monkeypatch):
    monkeypatch.setattr(settings, "chat_llm_raciocinio", "talvez")
    with pytest.raises(ErroConfiguracao, match="CHAT_LLM_RACIOCINIO 'talvez' inválido"):
        validar_provedor_chat_configurado()


def test_gemini_no_chat_aceita_so_o_modelo(chat_padrao, monkeypatch):
    monkeypatch.setattr(settings, "chat_llm_provider", "gemini")
    provedor = obter_provedor_chat()
    assert isinstance(provedor.base, ProvedorGemini)
    assert provedor.base.modelo == settings.modelo_llm
    monkeypatch.setattr(settings, "chat_modelos_permitidos", "gemini-outro")
    assert obter_provedor_chat("gemini-outro").base.modelo == "gemini-outro"


def test_cache_do_chat_e_independente_do_da_geracao(chat_padrao, monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", "gemini")
    geracao = obter_provedor()
    chat = obter_provedor_chat()
    assert isinstance(chat.base, ProvedorNvidia)

    # Trocar LLM_PROVIDER não mexe no chat...
    monkeypatch.setattr(settings, "llm_provider", "nvidia")
    assert isinstance(obter_provedor().base, ProvedorNvidia)
    assert obter_provedor_chat() is chat

    # ...e trocar CHAT_LLM_PROVIDER não mexe na geração.
    monkeypatch.setattr(settings, "llm_provider", "gemini")
    nova_geracao = obter_provedor()
    monkeypatch.setattr(settings, "chat_llm_provider", "gemini")
    assert isinstance(obter_provedor_chat().base, ProvedorGemini)
    assert obter_provedor() is nova_geracao
    assert geracao is not chat


# ── Retentativa e prazo ───────────────────────────────────────────────────────


class _Relogio:
    def __init__(self):
        self.agora = 1000.0
        self.esperas: list[float] = []

    def __call__(self) -> float:
        return self.agora

    def dormir(self, segundos: float) -> None:
        self.esperas.append(segundos)
        self.agora += segundos


class _Roteiro:
    """Devolve ou levanta os itens em ordem; cada chamada consome ``duracao`` segundos."""

    nome = "roteiro"

    def __init__(self, relogio, *itens, duracao: float = 0.0):
        self.relogio = relogio
        self.itens = list(itens)
        self.duracao = duracao
        self.timeouts: list[float] = []

    def gerar(self, mensagens, *, timeout_segundos):
        self.timeouts.append(timeout_segundos)
        self.relogio.agora += self.duracao
        item = self.itens.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item


def _chat(base, relogio) -> ProvedorDoChat:
    return ProvedorDoChat(base, relogio=relogio, dormir=relogio.dormir, sortear=lambda a, b: 1.0)


@pytest.mark.parametrize(
    "erro", [ErroLimiteTaxa("429"), ErroIndisponivel("503"), ErroTimeout("tempo")]
)
def test_uma_retentativa_em_erro_transitorio(erro):
    relogio = _Relogio()
    base = _Roteiro(relogio, erro, "resposta", duracao=2)
    assert _chat(base, relogio).gerar(MENSAGENS, timeout_segundos=45) == "resposta"
    assert len(base.timeouts) == 2
    assert relogio.esperas == [1.0]
    # O prazo é da pergunta: a segunda chamada só recebe o que sobrou (45 - 2 - 1).
    assert base.timeouts == [45, 42]


def test_no_maximo_uma_retentativa():
    relogio = _Relogio()
    base = _Roteiro(relogio, ErroIndisponivel("503"), ErroIndisponivel("503 de novo"), "nunca")
    with pytest.raises(ErroIndisponivel, match="de novo"):
        _chat(base, relogio).gerar(MENSAGENS, timeout_segundos=45)
    assert len(base.timeouts) == 2


@pytest.mark.parametrize(
    "erro",
    [
        ErroAutenticacao("401"),
        ErroModeloIndisponivel("404"),
        ErroConfiguracao("chave ausente"),
        ErroRespostaInvalida("vazia"),
    ],
)
def test_erro_nao_transitorio_nao_e_repetido(erro):
    relogio = _Relogio()
    base = _Roteiro(relogio, erro, "nunca")
    with pytest.raises(type(erro)):
        _chat(base, relogio).gerar(MENSAGENS, timeout_segundos=45)
    assert len(base.timeouts) == 1
    assert relogio.esperas == []


def test_sem_retentativa_quando_o_prazo_da_pergunta_acabou():
    relogio = _Relogio()
    # A primeira chamada estoura perto do fim do prazo: não sobra tempo para outra.
    base = _Roteiro(relogio, ErroTimeout("tempo"), "nunca", duracao=43)
    with pytest.raises(ErroTimeout):
        _chat(base, relogio).gerar(MENSAGENS, timeout_segundos=45)
    assert base.timeouts == [45]
    assert relogio.esperas == []


def test_usa_o_sono_falso_da_retentativa_da_geracao(espera_da_retentativa_falsa):
    """Sem injeção, o chat usa os mesmos ganchos de relógio e sono (trocados nos testes)."""
    base = _Roteiro(_Relogio(), ErroIndisponivel("503"), "ok")
    assert ProvedorDoChat(base).gerar(MENSAGENS, timeout_segundos=45) == "ok"
    assert len(espera_da_retentativa_falsa) == 1


def test_chat_dentro_de_um_job_ignora_e_preserva_os_limites_do_job():
    """Mesmo na thread de um job com o prazo já vencido, o chat usa o próprio prazo."""
    relogio = _Relogio()
    interrupcoes: list[int] = []

    def verificar():
        interrupcoes.append(1)

    with limites_da_geracao(prazo=relogio() - 100, verificar_interrupcao=verificar):
        antes = _limites.get()
        base = _Roteiro(relogio, ErroIndisponivel("503"), "resposta")
        assert _chat(base, relogio).gerar(MENSAGENS, timeout_segundos=45) == "resposta"
        assert _limites.get() is antes
    assert len(base.timeouts) == 2  # retentou apesar do prazo vencido do job
    assert interrupcoes == []  # e não chamou o cancelamento do job


def test_chat_em_outra_thread_nao_altera_o_job():
    relogio = _Relogio()
    limites_no_job: list = []
    pronto = threading.Event()
    seguir = threading.Event()

    def job():
        with limites_da_geracao(prazo=123.0):
            limites_no_job.append(_limites.get())
            pronto.set()
            seguir.wait(5)
            limites_no_job.append(_limites.get())

    thread = threading.Thread(target=job)
    thread.start()
    pronto.wait(5)
    base = _Roteiro(relogio, ErroIndisponivel("503"), "resposta")
    assert _chat(base, relogio).gerar(MENSAGENS, timeout_segundos=45) == "resposta"
    assert _limites.get().prazo is None  # a thread do chat não vê o prazo do job
    seguir.set()
    thread.join(5)
    assert limites_no_job[0] is limites_no_job[1]
    assert limites_no_job[1].prazo == 123.0


# ── Subida ────────────────────────────────────────────────────────────────────


def test_subida_sem_nenhuma_variavel_chat(chat_padrao, monkeypatch):
    for nome in VARIAVEIS_CHAT:
        monkeypatch.delenv(nome, raising=False)
    monkeypatch.setattr(settings, "nvidia_nim_api_key", SecretStr(""))  # a chave não é exigida na subida
    with TestClient(app) as client:
        assert client.get("/api/v1/health").status_code == 200


def test_provedor_do_chat_desconhecido_impede_a_subida(chat_padrao, monkeypatch):
    monkeypatch.setattr(settings, "chat_llm_provider", "inexistente")
    with pytest.raises(ProvedorDesconhecido, match="CHAT_LLM_PROVIDER 'inexistente'"):
        with TestClient(app):
            pass


def test_raciocinio_do_chat_invalido_impede_a_subida(chat_padrao, monkeypatch):
    monkeypatch.setattr(settings, "chat_llm_raciocinio", "talvez")
    with pytest.raises(ErroConfiguracao, match="CHAT_LLM_RACIOCINIO"):
        with TestClient(app):
            pass
