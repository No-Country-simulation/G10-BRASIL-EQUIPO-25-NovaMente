"""Testes da subida segura do SQLite (issue #70)."""

from __future__ import annotations

import os
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from app.core.config import settings
from app.core.preparo_banco import (
    caminho_de_database_url,
    caminhos_do_banco,
    preparar_banco,
)


def _tabelas(caminho: Path) -> set[str]:
    with closing(sqlite3.connect(caminho)) as conexao:
        linhas = conexao.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
    return {nome for (nome,) in linhas}


# ── Caminho da DATABASE_URL ───────────────────────────────────────────────────


@pytest.mark.parametrize(
    "url,esperado",
    [
        ("sqlite:///./data/novamente.db", Path("./data/novamente.db")),
        ("sqlite:///relativo.db", Path("relativo.db")),
        ("sqlite:////var/dados/novamente.db", Path("/var/dados/novamente.db")),
        ("sqlite:////var/dados/n.db?timeout=5", Path("/var/dados/n.db")),
        ("sqlite://", None),
        ("sqlite:///:memory:", None),
        ("postgresql://u:s@host/banco", None),
        ("isto não é uma url", None),
    ],
)
def test_caminho_de_database_url(url, esperado):
    assert caminho_de_database_url(url) == esperado


def test_caminhos_do_banco_nao_repete_o_mesmo_arquivo(tmp_path):
    arquivo = tmp_path / "novamente.db"

    um = caminhos_do_banco(str(arquivo), f"sqlite:///{arquivo}")
    dois = caminhos_do_banco(str(arquivo), f"sqlite:///{tmp_path}/outro.db")

    assert [variavel for variavel, _ in um] == ["DB_PATH"]
    assert [variavel for variavel, _ in dois] == ["DB_PATH", "DATABASE_URL"]


# ── Subida com volume vazio ───────────────────────────────────────────────────


def test_preparar_cria_pasta_e_arquivo_para_db_path_e_database_url(tmp_path, monkeypatch):
    db_path = tmp_path / "volume" / "jobs" / "novamente.db"
    catalogo = tmp_path / "volume" / "catalogo" / "catalogo.db"
    monkeypatch.setattr(settings, "db_path", str(db_path))
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{catalogo}")

    preparar_banco()

    assert db_path.is_file() and db_path.stat().st_size == 0
    assert catalogo.is_file() and catalogo.stat().st_size == 0


def test_preparar_aceita_database_url_relativa(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "x" / "jobs.db"))
    monkeypatch.setattr(settings, "database_url", "sqlite:///./rel/catalogo.db")

    preparar_banco()

    assert (tmp_path / "rel" / "catalogo.db").is_file()


def test_subida_com_volume_vazio_cria_o_esquema_e_atende(tmp_path, monkeypatch):
    """Pasta do volume inexistente: o backend sobe, cria o esquema e responde."""
    import app.main as principal

    arquivo = tmp_path / "volume-novo" / "dados" / "novamente.db"
    monkeypatch.setattr(settings, "db_path", str(arquivo))
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{arquivo}")
    motor = create_engine(f"sqlite:///{arquivo}", connect_args={"check_same_thread": False})
    monkeypatch.setattr(principal, "engine", motor)
    assert not arquivo.parent.exists()

    try:
        with TestClient(principal.app) as cliente:
            assert arquivo.is_file()
            assert {"jobs", "pacotes", "alunos", "materiais", "vinculos"} <= _tabelas(arquivo)
            assert cliente.get("/api/v1/health").json()["banco"] == "ok"
    finally:
        motor.dispose()


def test_preparar_e_idempotente_e_nao_toca_em_dados_existentes(tmp_path, monkeypatch):
    arquivo = tmp_path / "novamente.db"
    with closing(sqlite3.connect(arquivo)) as conexao:
        conexao.execute("CREATE TABLE dados (valor TEXT)")
        conexao.executemany("INSERT INTO dados VALUES (?)", [("a",), ("b",)])
        conexao.commit()
    antes = arquivo.read_bytes()
    monkeypatch.setattr(settings, "db_path", str(arquivo))
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{arquivo}")

    preparar_banco()
    preparar_banco()

    assert arquivo.read_bytes() == antes
    assert [f.name for f in tmp_path.iterdir()] == ["novamente.db"]


# ── Caminhos inválidos ────────────────────────────────────────────────────────


def test_pai_do_caminho_e_arquivo_comum_falha_com_mensagem_clara(tmp_path, monkeypatch):
    arquivo_comum = tmp_path / "nao-e-pasta"
    arquivo_comum.write_text("conteúdo")
    monkeypatch.setattr(settings, "db_path", str(arquivo_comum / "novamente.db"))

    with pytest.raises(RuntimeError) as erro:
        preparar_banco()

    mensagem = str(erro.value)
    assert "Não foi possível criar a pasta do banco de dados" in mensagem
    assert "DB_PATH" in mensagem
    assert arquivo_comum.read_text() == "conteúdo"


def test_database_url_com_pai_invalido_cita_a_variavel(tmp_path, monkeypatch):
    arquivo_comum = tmp_path / "nao-e-pasta"
    arquivo_comum.write_text("x")
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "ok" / "jobs.db"))
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{arquivo_comum}/catalogo.db")

    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        preparar_banco()


def test_db_path_apontando_para_pasta_falha_com_mensagem_clara(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "db_path", str(tmp_path))

    with pytest.raises(RuntimeError, match="aponta para uma pasta"):
        preparar_banco()


def test_arquivo_que_nao_e_banco_falha_sem_alterar_o_arquivo(tmp_path, monkeypatch):
    arquivo = tmp_path / "novamente.db"
    arquivo.write_bytes(b"isto nao e um banco sqlite " * 200)
    antes = arquivo.read_bytes()
    monkeypatch.setattr(settings, "db_path", str(arquivo))

    with pytest.raises(RuntimeError, match="banco SQLite válido"):
        preparar_banco()

    assert arquivo.read_bytes() == antes


def test_pasta_que_nao_aceita_gravacao_falha_com_mensagem_clara(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "novamente.db"))

    def sem_gravacao(*_args, **_kwargs):
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr(tempfile, "TemporaryFile", sem_gravacao)

    with pytest.raises(RuntimeError, match="não aceita gravação"):
        preparar_banco()


def test_mkdir_negado_vira_erro_claro(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "novo" / "novamente.db"))

    def negado(*_args, **_kwargs):
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr(Path, "mkdir", negado)

    with pytest.raises(RuntimeError, match="Confira se o volume está montado"):
        preparar_banco()


@pytest.mark.skipif(
    not hasattr(os, "geteuid") or os.geteuid() == 0,
    reason="como root, as permissões POSIX não impedem a escrita",
)
def test_pasta_sem_permissao_de_escrita_falha_com_mensagem_clara(tmp_path, monkeypatch):
    pasta = tmp_path / "somente-leitura"
    pasta.mkdir()
    pasta.chmod(0o500)
    monkeypatch.setattr(settings, "db_path", str(pasta / "novamente.db"))
    try:
        with pytest.raises(RuntimeError, match="DB_PATH"):
            preparar_banco()
    finally:
        pasta.chmod(0o700)


def test_subida_do_app_com_caminho_invalido_falha_antes_de_criar_o_esquema(tmp_path, monkeypatch):
    from app.main import app

    arquivo_comum = tmp_path / "nao-e-pasta"
    arquivo_comum.write_text("x")
    monkeypatch.setattr(settings, "db_path", str(arquivo_comum / "novamente.db"))

    with pytest.raises(RuntimeError, match="Não foi possível criar a pasta do banco de dados"):
        with TestClient(app):
            pass


def test_arquivo_sem_permissao_de_escrita_falha_com_mensagem_clara(tmp_path, monkeypatch):
    """Simula o arquivo somente leitura (como root, chmod não impede a escrita)."""
    arquivo = tmp_path / "novamente.db"
    with closing(sqlite3.connect(arquivo)) as conexao:
        conexao.execute("CREATE TABLE dados (valor TEXT)")
    monkeypatch.setattr(settings, "db_path", str(arquivo))
    monkeypatch.setattr(os, "access", lambda *_args, **_kwargs: False)

    with pytest.raises(RuntimeError, match="não pôde ser aberto para escrita"):
        preparar_banco()
