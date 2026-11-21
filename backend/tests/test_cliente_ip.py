"""ip_do_cliente: X-Forwarded-For só com CONFIAR_X_FORWARDED_FOR ligado."""

from __future__ import annotations

import pytest
from starlette.requests import Request

from app.core import cliente
from app.core.config import settings

IP_CONEXAO = "10.9.8.7"


def _requisicao(xff: str | None = None, client=(IP_CONEXAO, 5000)) -> Request:
    headers = [] if xff is None else [(b"x-forwarded-for", xff.encode())]
    return Request({"type": "http", "method": "GET", "path": "/", "headers": headers, "client": client})


@pytest.fixture
def confiar(monkeypatch):
    monkeypatch.setattr(settings, "confiar_x_forwarded_for", True)


def test_desligada_ignora_cabecalho_forjado():
    assert settings.confiar_x_forwarded_for is False
    assert cliente.ip_do_cliente(_requisicao("1.2.3.4")) == IP_CONEXAO


def test_ligada_usa_o_ultimo_ip(confiar):
    # A última entrada é a do proxy confiável; as anteriores vêm do cliente.
    assert cliente.ip_do_cliente(_requisicao("1.2.3.4, 10.0.0.1, 203.0.113.5")) == "203.0.113.5"
    assert cliente.ip_do_cliente(_requisicao("  198.51.100.2  ")) == "198.51.100.2"


@pytest.mark.parametrize("xff", ["nao-e-ip", "", " , ", "999.1.1.1", "1.2.3.4:8080", "1.2.3.4, "])
def test_ligada_valor_invalido_ou_lista_vazia_cai_para_a_conexao(confiar, xff):
    assert cliente.ip_do_cliente(_requisicao(xff)) == IP_CONEXAO


def test_ligada_aceita_ipv6(confiar):
    assert cliente.ip_do_cliente(_requisicao("10.0.0.1, 2001:db8::1")) == "2001:db8::1"


def test_ligada_sem_cabecalho_usa_a_conexao(confiar):
    assert cliente.ip_do_cliente(_requisicao()) == IP_CONEXAO


def test_sem_conexao_conhecida(confiar):
    assert cliente.ip_do_cliente(_requisicao(client=None)) == cliente.IP_DESCONHECIDO


@pytest.mark.parametrize("valor,esperado", [("", False), ("true", True), ("false", False)])
def test_variavel_vazia_vale_o_padrao(monkeypatch, valor, esperado):
    from app.core.config import Settings

    monkeypatch.setenv("CONFIAR_X_FORWARDED_FOR", valor)
    assert Settings(_env_file=None).confiar_x_forwarded_for is esperado
