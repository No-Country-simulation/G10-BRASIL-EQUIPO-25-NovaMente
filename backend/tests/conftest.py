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
def chroma_isolado(tmp_path, monkeypatch):
    """Nenhum teste toca o CHROMA_DIR padrão.

    O worker (limpeza ao fim do job) e o lifespan (varredura na subida) usam o
    Chroma. Sem cliente injetado, eles só abrem a pasta configurada se ela
    existir; aqui ela aponta para uma pasta temporária que não existe. Quem
    precisa de Chroma de verdade pede ``chroma_temporario``.
    """
    from app.rag import armazenamento, config

    monkeypatch.setattr(config, "CHROMA_DIR", str(tmp_path / "chroma-padrao"))
    armazenamento.definir_cliente(None)
    yield tmp_path / "chroma-padrao"
    armazenamento.definir_cliente(None)
