"""Configuração do pytest para o backend."""

import sys
import os

import pytest

# Adiciona o diretório backend ao path para que os imports funcionem
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(autouse=True)
def banco_temporario(tmp_path, monkeypatch):
    """Cada teste usa um SQLite próprio, pelo mesmo settings.db_path que o código lê."""
    from app.core.config import settings

    caminho = tmp_path / "novamente.sqlite3"
    monkeypatch.setattr(settings, "db_path", str(caminho))
    return caminho


@pytest.fixture(autouse=True)
def fabrica_llm_isolada(monkeypatch):
    """Provedores registrados num teste não vazam para o próximo."""
    from app.llm import fabrica

    monkeypatch.setattr(fabrica, "_construtores", dict(fabrica._construtores))
    fabrica.redefinir_provedor()
    yield
    fabrica.redefinir_provedor()
