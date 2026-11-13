"""Retentativa das falhas transitórias do LLM (app/llm/retentativa.py).

Relógio, sono e sorteio são falsos: nenhum teste dorme nem sorteia de verdade.
"""

from __future__ import annotations

import logging

import pytest
from pydantic import ValidationError

from app.core.config import Settings, settings
from app.llm import (
    ErroConfiguracao,
    ErroIndisponivel,
    ErroLimiteTaxa,
    ErroLLM,
    ErroRespostaInvalida,
    ErroTimeout,
    Mensagem,
    ProvedorDesconhecido,
    limites_da_geracao,
)
from app.llm.retentativa import (
    ESPERA_MAXIMA_SEGUNDOS,
    FATIA_ESPERA_SEGUNDOS,
    JITTER,
    ProvedorComRetentativa,
)

TEXTO_CRU = "conteudo-do-documento-456"
MENSAGENS = [Mensagem("user", f"Explique {TEXTO_CRU}")]
TIMEOUT = 120


class _Relogio:
    """Relógio monotônico falso; ``dormir`` só avança o tempo."""

    def __init__(self):
        self.agora = 1000.0
        self.fatias: list[float] = []

    def __call__(self) -> float:
        return self.agora

    def dormir(self, segundos: float) -> None:
        self.fatias.append(segundos)
        self.agora += segundos


class _ProvedorRoteiro:
    """Devolve, em ordem, os itens do roteiro (texto ou exceção); o último se repete."""

    nome = "roteiro"

    def __init__(self, relogio: _Relogio, *itens, duracao: float = 0.0):
        self.relogio = relogio
        self.itens = itens
        self.duracao = duracao  # quanto tempo cada chamada consome no relógio falso
        self.inicios: list[float] = []

    @property
    def chamadas(self) -> int:
        return len(self.inicios)

    def gerar(self, mensagens, *, timeout_segundos):
        self.inicios.append(self.relogio())
        self.relogio.agora += self.duracao
        item = self.itens[min(self.chamadas, len(self.itens)) - 1]
        if isinstance(item, BaseException):
            raise item
        return item


@pytest.fixture
def relogio():
    return _Relogio()


@pytest.fixture
def padroes(monkeypatch):
    monkeypatch.setattr(settings, "llm_tentativas", 3)
    monkeypatch.setattr(settings, "llm_espera_inicial_segundos", 2.0)


def _embrulhar(base, relogio, sorteios=None):
    sorteios = list(sorteios or [])
    pedidos = []

    def sortear(minimo, maximo):
        pedidos.append((minimo, maximo))
        return sorteios.pop(0) if sorteios else 1.0

    provedor = ProvedorComRetentativa(
        base, relogio=relogio, dormir=relogio.dormir, sortear=sortear
    )
    provedor.pedidos_de_sorteio = pedidos
    return provedor


def _esperas(base) -> list[float]:
    """Intervalo entre o início de chamadas seguidas (chamadas instantâneas)."""
    return [b - a for a, b in zip(base.inicios, base.inicios[1:])]


# ── O que é e o que não é retentado ──────────────────────────────────────────


@pytest.mark.usefixtures("padroes")
@pytest.mark.parametrize("erro", [ErroIndisponivel("503"), ErroLimiteTaxa("429"), ErroTimeout("t")])
def test_transitorio_seguido_de_sucesso(relogio, erro):
    base = _ProvedorRoteiro(relogio, erro, "resposta")
    assert _embrulhar(base, relogio).gerar(MENSAGENS, timeout_segundos=TIMEOUT) == "resposta"
    assert base.chamadas == 2


@pytest.mark.usefixtures("padroes")
@pytest.mark.parametrize("classe", [ErroIndisponivel, ErroLimiteTaxa, ErroTimeout])
def test_transitorio_em_todas_as_tentativas_sobe_o_ultimo_erro(relogio, monkeypatch, classe):
    monkeypatch.setattr(settings, "llm_tentativas", 4)
    base = _ProvedorRoteiro(relogio, classe("falha"))
    with pytest.raises(classe):
        _embrulhar(base, relogio).gerar(MENSAGENS, timeout_segundos=TIMEOUT)
    assert base.chamadas == 4


@pytest.mark.usefixtures("padroes")
@pytest.mark.parametrize(
    "erro",
    [
        ErroConfiguracao("401"),
        ProvedorDesconhecido("x"),
        ErroRespostaInvalida("vazia"),
        ErroLLM("desconhecido"),
    ],
    ids=["configuracao", "provedor-desconhecido", "resposta-invalida", "erro-generico"],
)
def test_nao_transitorio_falha_na_primeira_sem_esperar(relogio, erro):
    base = _ProvedorRoteiro(relogio, erro, "nunca chega aqui")
    with pytest.raises(type(erro)):
        _embrulhar(base, relogio).gerar(MENSAGENS, timeout_segundos=TIMEOUT)
    assert base.chamadas == 1
    assert relogio.fatias == []


def test_repassa_mensagens_e_timeout_e_mantem_o_nome(relogio):
    recebidos = []

    class _Base:
        nome = "base"

        def gerar(self, mensagens, *, timeout_segundos):
            recebidos.append((mensagens, timeout_segundos))
            return "ok"

    provedor = _embrulhar(_Base(), relogio)
    assert provedor.nome == "base"
    assert provedor.gerar(MENSAGENS, timeout_segundos=45) == "ok"
    assert recebidos == [(MENSAGENS, 45)]


# ── Espera: backoff, jitter e teto ───────────────────────────────────────────


def test_espera_dobra_com_jitter(relogio, monkeypatch):
    monkeypatch.setattr(settings, "llm_tentativas", 3)
    monkeypatch.setattr(settings, "llm_espera_inicial_segundos", 2.0)
    base = _ProvedorRoteiro(relogio, ErroIndisponivel("503"))
    provedor = _embrulhar(base, relogio, sorteios=[1.2, 0.8])
    with pytest.raises(ErroIndisponivel):
        provedor.gerar(MENSAGENS, timeout_segundos=TIMEOUT)
    assert _esperas(base) == pytest.approx([2.0 * 1.2, 4.0 * 0.8])
    assert provedor.pedidos_de_sorteio == [(1 - JITTER, 1 + JITTER)] * 2
    assert max(relogio.fatias) <= FATIA_ESPERA_SEGUNDOS


def test_espera_respeita_o_teto(relogio, monkeypatch):
    monkeypatch.setattr(settings, "llm_tentativas", 5)
    monkeypatch.setattr(settings, "llm_espera_inicial_segundos", 10.0)
    base = _ProvedorRoteiro(relogio, ErroIndisponivel("503"))
    with pytest.raises(ErroIndisponivel):
        _embrulhar(base, relogio, sorteios=[1.2] * 4).gerar(MENSAGENS, timeout_segundos=TIMEOUT)
    assert ESPERA_MAXIMA_SEGUNDOS == 30.0
    assert _esperas(base) == pytest.approx([12.0, 24.0, 30.0, 30.0])


# ── Prazo do job ─────────────────────────────────────────────────────────────


@pytest.mark.usefixtures("padroes")
def test_nao_retenta_se_o_prazo_nao_comporta_outra_chamada(relogio, caplog):
    base = _ProvedorRoteiro(relogio, ErroIndisponivel("503"), "resposta")
    # Falta 1 s para caber a espera (2 s) mais uma chamada inteira (120 s).
    with limites_da_geracao(prazo=relogio() + 2 + TIMEOUT - 1):
        with caplog.at_level(logging.WARNING, logger="app.llm.retentativa"):
            with pytest.raises(ErroIndisponivel):
                _embrulhar(base, relogio).gerar(MENSAGENS, timeout_segundos=TIMEOUT)
    assert base.chamadas == 1
    assert relogio.fatias == []
    assert "prazo do job não comporta outra chamada" in caplog.text


@pytest.mark.usefixtures("padroes")
def test_retenta_enquanto_o_prazo_comporta(relogio):
    base = _ProvedorRoteiro(relogio, ErroIndisponivel("503"))
    # Cabe exatamente uma retentativa (2 s + 120 s); a segunda (4 s + 120 s) não.
    with limites_da_geracao(prazo=relogio() + 2 + TIMEOUT):
        with pytest.raises(ErroIndisponivel):
            _embrulhar(base, relogio).gerar(MENSAGENS, timeout_segundos=TIMEOUT)
    assert base.chamadas == 2


@pytest.mark.usefixtures("padroes")
def test_timeouts_seguidos_param_no_prazo_padrao_do_job(relogio):
    """Com os padrões (120 s por chamada, job de 300 s), cabem só dois timeouts."""
    base = _ProvedorRoteiro(relogio, ErroTimeout("t"), duracao=TIMEOUT)
    with limites_da_geracao(prazo=relogio() + 300):
        with pytest.raises(ErroTimeout):
            _embrulhar(base, relogio).gerar(MENSAGENS, timeout_segundos=TIMEOUT)
    assert base.chamadas == 2
    assert relogio() <= base.inicios[0] + 300


@pytest.mark.usefixtures("padroes")
def test_sem_limites_vale_so_o_numero_de_tentativas(relogio):
    base = _ProvedorRoteiro(relogio, ErroTimeout("t"), duracao=TIMEOUT)
    with pytest.raises(ErroTimeout):
        _embrulhar(base, relogio).gerar(MENSAGENS, timeout_segundos=TIMEOUT)
    assert base.chamadas == 3


def test_limites_valem_so_dentro_do_bloco(relogio, monkeypatch):
    monkeypatch.setattr(settings, "llm_tentativas", 2)
    with limites_da_geracao(prazo=relogio()):
        pass
    base = _ProvedorRoteiro(relogio, ErroIndisponivel("503"), "resposta")
    assert _embrulhar(base, relogio).gerar(MENSAGENS, timeout_segundos=TIMEOUT) == "resposta"


# ── Cancelamento durante a espera ────────────────────────────────────────────


@pytest.mark.usefixtures("padroes")
def test_cancelamento_interrompe_a_espera_em_fatias(relogio):
    checagens = []

    def verificar():
        checagens.append(relogio())
        if len(checagens) == 3:
            raise InterruptedError("Cancelado pelo usuário.")

    base = _ProvedorRoteiro(relogio, ErroIndisponivel("503"), "resposta")
    with limites_da_geracao(verificar_interrupcao=verificar):
        with pytest.raises(InterruptedError):
            _embrulhar(base, relogio).gerar(MENSAGENS, timeout_segundos=TIMEOUT)
    assert base.chamadas == 1  # não chegou a tentar de novo
    assert relogio.fatias == [FATIA_ESPERA_SEGUNDOS] * 2  # parou na 3ª checagem, antes de 2 s


# ── Configuração ─────────────────────────────────────────────────────────────


def test_padroes_de_configuracao(monkeypatch):
    monkeypatch.delenv("LLM_TENTATIVAS", raising=False)
    monkeypatch.delenv("LLM_ESPERA_INICIAL_SEGUNDOS", raising=False)
    config = Settings(_env_file=None)
    assert config.llm_tentativas == 3
    assert config.llm_espera_inicial_segundos == 2.0


def test_configuracao_vem_do_ambiente(monkeypatch):
    monkeypatch.setenv("LLM_TENTATIVAS", "5")
    monkeypatch.setenv("LLM_ESPERA_INICIAL_SEGUNDOS", "0.5")
    config = Settings(_env_file=None)
    assert config.llm_tentativas == 5
    assert config.llm_espera_inicial_segundos == 0.5


@pytest.mark.parametrize(
    "variavel,valor",
    [
        ("LLM_TENTATIVAS", "0"),
        ("LLM_TENTATIVAS", "-2"),
        ("LLM_ESPERA_INICIAL_SEGUNDOS", "-1"),
    ],
)
def test_configuracao_invalida_impede_a_subida(monkeypatch, variavel, valor):
    monkeypatch.setenv(variavel, valor)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_espera_zero_retenta_sem_dormir(relogio, monkeypatch):
    monkeypatch.setenv("LLM_ESPERA_INICIAL_SEGUNDOS", "0")
    assert Settings(_env_file=None).llm_espera_inicial_segundos == 0
    monkeypatch.setattr(settings, "llm_tentativas", 3)
    monkeypatch.setattr(settings, "llm_espera_inicial_segundos", 0.0)
    base = _ProvedorRoteiro(relogio, ErroIndisponivel("503"), ErroIndisponivel("503"), "ok")
    assert _embrulhar(base, relogio).gerar(MENSAGENS, timeout_segundos=TIMEOUT) == "ok"
    assert base.chamadas == 3
    assert relogio.fatias == []


@pytest.mark.parametrize("tentativas", [0, -3])
def test_tentativas_invalidas_em_tempo_de_execucao_valem_uma(relogio, monkeypatch, tentativas):
    """Se ``settings`` for alterado sem validação, ainda há uma chamada e nenhuma espera."""
    monkeypatch.setattr(settings, "llm_tentativas", tentativas)
    monkeypatch.setattr(settings, "llm_espera_inicial_segundos", -5.0)
    base = _ProvedorRoteiro(relogio, ErroIndisponivel("503"))
    with pytest.raises(ErroIndisponivel):
        _embrulhar(base, relogio).gerar(MENSAGENS, timeout_segundos=TIMEOUT)
    assert base.chamadas == 1
    assert relogio.fatias == []


# ── Log ──────────────────────────────────────────────────────────────────────


@pytest.mark.usefixtures("padroes")
def test_log_tem_categoria_e_tentativa_sem_conteudo(relogio, caplog, monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "chave-falsa-789")
    base = _ProvedorRoteiro(
        relogio, ErroLimiteTaxa(f"429 {TEXTO_CRU}"), ErroIndisponivel(f"503 {TEXTO_CRU}")
    )
    with caplog.at_level(logging.WARNING, logger="app.llm.retentativa"):
        with pytest.raises(ErroIndisponivel):
            _embrulhar(base, relogio).gerar(MENSAGENS, timeout_segundos=TIMEOUT)
    linhas = [r.getMessage() for r in caplog.records]
    assert len(linhas) == 3
    assert "roteiro (ErroLimiteTaxa, tentativa 1 de 3)" in linhas[0]
    assert "nova tentativa em 2.0s" in linhas[0]
    assert "roteiro (ErroIndisponivel, tentativa 2 de 3)" in linhas[1]
    assert "tentativa 3 de 3" in linhas[2] and "tentativas esgotadas" in linhas[2]
    assert TEXTO_CRU not in caplog.text
    assert "chave-falsa-789" not in caplog.text
