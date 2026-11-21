"""Máscara de segredos nos logs (app/core/redacao_logs.py)."""

from __future__ import annotations

import logging

import pytest

from app.core import redacao_logs
from app.core.config import settings

SEGREDO = "segredo-de-teste-0123456789"


@pytest.fixture(autouse=True)
def ambiente(monkeypatch):
    for nome in list(__import__("os").environ):
        if redacao_logs._NOME_SECRETO.search(nome):
            monkeypatch.delenv(nome)
    monkeypatch.setattr(settings, "google_api_key", "")
    redacao_logs.instalar_redacao_de_segredos()


def _logar(caplog, mensagem, *args, **kw):
    caplog.set_level(logging.DEBUG)
    logging.getLogger("teste.redacao").error(mensagem, *args, **kw)
    return caplog.text


def test_mascara_a_chave_da_configuracao_na_mensagem_e_nos_argumentos(monkeypatch, caplog):
    monkeypatch.setattr(settings, "google_api_key", SEGREDO)
    texto = _logar(caplog, f"direto {SEGREDO}; formatado %s; repr %r", SEGREDO, SEGREDO)
    assert SEGREDO not in texto
    assert texto.count("***") == 3


def test_mascara_variaveis_de_ambiente_com_nome_de_segredo(monkeypatch, caplog):
    for nome in ("NVIDIA_API_KEY", "OCI_PRIVATE_KEY", "MEU_TOKEN", "DB_PASSWORD"):
        monkeypatch.setenv(nome, f"valor-{nome}-1234567")
    texto = _logar(caplog, "a %s b %s c %s d %s", "valor-NVIDIA_API_KEY-1234567",
                   "valor-OCI_PRIVATE_KEY-1234567", "valor-MEU_TOKEN-1234567",
                   "valor-DB_PASSWORD-1234567")
    assert "valor-" not in texto


def test_mascara_o_texto_de_excecao_e_a_causa_no_traceback(monkeypatch, caplog):
    monkeypatch.setattr(settings, "google_api_key", SEGREDO)
    caplog.set_level(logging.DEBUG)
    try:
        try:
            raise ValueError(f"url com ?key={SEGREDO}")
        except ValueError as causa:
            raise RuntimeError("falha externa") from causa
    except RuntimeError:
        logging.getLogger("teste.redacao").exception("falhou: %s", RuntimeError(SEGREDO))
    assert SEGREDO not in caplog.text
    assert "?key=***" in caplog.text
    assert "falha externa" in caplog.text  # o resto do traceback continua legível


def test_mascara_argumentos_em_dicionario(monkeypatch, caplog):
    monkeypatch.setattr(settings, "google_api_key", SEGREDO)
    caplog.set_level(logging.DEBUG)
    logging.getLogger("teste.redacao").error("valor=%(chave)s n=%(n)d", {"chave": SEGREDO, "n": 3})
    assert SEGREDO not in caplog.text
    assert "n=3" in caplog.text


def test_nao_altera_logs_sem_segredo(monkeypatch, caplog):
    monkeypatch.setattr(settings, "google_api_key", SEGREDO)
    texto = _logar(caplog, "job %s com %d trechos (%.1f%%)", "abc", 3, 42.5)
    assert "job abc com 3 trechos (42.5%)" in texto


def test_ignora_valores_curtos_para_nao_mascarar_texto_comum(monkeypatch, caplog):
    monkeypatch.setenv("APP_TOKEN", "abc")
    texto = _logar(caplog, "abc continua visível")
    assert "abc continua visível" in texto
    assert redacao_logs.segredos_conhecidos() == []


def test_segredos_mais_longos_primeiro(monkeypatch):
    monkeypatch.setattr(settings, "google_api_key", "prefixo-comum-12345")
    monkeypatch.setenv("OUTRA_API_KEY", "prefixo-comum-12345-completo")
    assert redacao_logs.mascarar("x prefixo-comum-12345-completo y") == "x *** y"


def test_instalar_duas_vezes_nao_empilha_fabricas():
    fabrica = logging.getLogRecordFactory()
    redacao_logs.instalar_redacao_de_segredos()
    assert logging.getLogRecordFactory() is fabrica


def test_falha_na_mascara_nao_derruba_o_log(monkeypatch, caplog):
    def quebrar():
        raise RuntimeError("falha")

    monkeypatch.setattr(redacao_logs, "segredos_conhecidos", quebrar)
    texto = _logar(caplog, "segue funcionando")
    assert "segue funcionando" in texto
