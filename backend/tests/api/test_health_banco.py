"""Testes do campo ``banco`` do GET /health (issue #70)."""

from __future__ import annotations

import sqlite3
import time
from contextlib import closing
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app

URL = "/api/v1/health"
CAMPOS = {"status", "versao", "oci", "llm", "banco", "verificado_em"}


@pytest.fixture
def cliente_health():
    return TestClient(app)  # sem lifespan: o /health não depende da subida


@pytest.fixture
def banco_existente(banco_temporario):
    """Cria o arquivo do DB_PATH de teste (o autouse só define o caminho)."""
    with closing(sqlite3.connect(banco_temporario)) as conexao:
        conexao.execute("CREATE TABLE t (x INTEGER)")
        conexao.commit()
    return banco_temporario


@pytest.fixture
def dependencias_ok(monkeypatch):
    monkeypatch.setattr(settings, "google_api_key", "chave-de-teste")
    monkeypatch.setattr("app.services.oci.obter_status", lambda: SimpleNamespace(configurado=True))


def test_health_com_banco_acessivel(cliente_health, banco_existente):
    resp = cliente_health.get(URL)

    assert resp.status_code == 200
    assert resp.json()["banco"] == "ok"


def test_health_mantem_os_campos_existentes_e_acrescenta_so_banco(cliente_health, banco_existente):
    corpo = cliente_health.get(URL).json()

    assert set(corpo) == CAMPOS
    assert corpo["oci"] in ("ok", "indisponivel")
    assert corpo["llm"] in ("ok", "indisponivel")
    assert corpo["status"] in ("ok", "degraded")


def test_status_geral_ok_quando_todas_as_dependencias_estao_ok(
    cliente_health, banco_existente, dependencias_ok
):
    corpo = cliente_health.get(URL).json()

    assert (corpo["status"], corpo["oci"], corpo["llm"], corpo["banco"]) == ("ok", "ok", "ok", "ok")


def test_banco_ausente_e_indisponivel_e_o_status_fica_degraded_com_200(
    cliente_health, banco_temporario, dependencias_ok
):
    assert not banco_temporario.exists()  # o arquivo do DB_PATH não existe

    resp = cliente_health.get(URL)

    assert resp.status_code == 200
    corpo = resp.json()
    assert corpo["banco"] == "indisponivel"
    assert corpo["status"] == "degraded"
    assert (corpo["oci"], corpo["llm"]) == ("ok", "ok")
    assert not banco_temporario.exists()  # o health não cria o arquivo


def test_consulta_do_health_nao_apaga_nem_altera_o_banco(cliente_health, banco_existente):
    antes = banco_existente.read_bytes()

    cliente_health.get(URL)
    cliente_health.get(URL)

    assert banco_existente.read_bytes() == antes


def test_caminho_com_pai_que_e_arquivo_e_indisponivel(cliente_health, tmp_path, monkeypatch):
    arquivo_comum = tmp_path / "arquivo-comum"
    arquivo_comum.write_text("x")
    monkeypatch.setattr(settings, "db_path", str(arquivo_comum / "novamente.db"))

    assert cliente_health.get(URL).json()["banco"] == "indisponivel"


def test_arquivo_que_nao_e_banco_e_indisponivel(cliente_health, banco_temporario):
    banco_temporario.write_bytes(b"isto nao e um banco sqlite " * 200)

    assert cliente_health.get(URL).json()["banco"] == "indisponivel"


def test_catalogo_em_outro_arquivo_ausente_tambem_marca_indisponivel(
    cliente_health, banco_existente, tmp_path, monkeypatch
):
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{tmp_path}/catalogo-que-sumiu.db")

    assert cliente_health.get(URL).json()["banco"] == "indisponivel"


def test_resposta_nao_expoe_caminho_nem_mensagem_da_excecao(
    cliente_health, banco_existente, monkeypatch
):
    segredo = "/volume-secreto/novamente.db"

    def quebra(*_args, **_kwargs):
        raise sqlite3.OperationalError(f"unable to open database file {segredo}")

    monkeypatch.setattr("app.api.v1.routers.health.sqlite3.connect", quebra)

    resp = cliente_health.get(URL)

    assert resp.status_code == 200
    assert resp.json()["banco"] == "indisponivel"
    for trecho in (segredo, "volume-secreto", "unable to open", str(banco_existente.parent)):
        assert trecho not in resp.text


def test_resposta_com_banco_ok_tambem_nao_expoe_caminho(cliente_health, banco_existente):
    texto = cliente_health.get(URL).text

    assert str(banco_existente.parent) not in texto
    assert ".db" not in texto and ".sqlite" not in texto


def test_banco_travado_responde_rapido_como_indisponivel(cliente_health, banco_existente):
    """Outro processo segura o banco com lock exclusivo: o health não fica preso."""
    trava = sqlite3.connect(banco_existente, isolation_level=None)
    try:
        trava.execute("BEGIN EXCLUSIVE")
        inicio = time.monotonic()
        resp = cliente_health.get(URL)
        duracao = time.monotonic() - inicio
    finally:
        trava.execute("ROLLBACK")
        trava.close()

    assert resp.status_code == 200
    assert resp.json()["banco"] == "indisponivel"
    assert duracao < 5
