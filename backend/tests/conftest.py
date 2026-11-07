"""Configuração do pytest para o backend."""

import sys
import os
import uuid
from urllib.parse import quote

import pytest

# Adiciona o diretório backend ao path para que os imports funcionem
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _com_search_path(url: str, schema: str) -> str:
    """Acrescenta à URL a opção do libpq que fixa o search_path da conexão."""
    separador = "&" if "?" in url else "?"
    return f"{url}{separador}options={quote(f'-c search_path={schema}')}"


@pytest.fixture(autouse=True)
def banco_isolado(monkeypatch):
    """Cada teste usa um schema próprio no PostgreSQL de DATABASE_URL.

    O schema só é criado se o teste abrir o pool do repositório e é apagado
    no fim. Sem DATABASE_URL nada é trocado: os testes que usam o repositório
    falham com a mensagem "DATABASE_URL não definida" (sem skip silencioso).
    """
    import psycopg

    from app.core.config import settings
    from app.services import repositorio

    base = settings.database_url
    if not base:
        yield None
        return

    schema = f"teste_{uuid.uuid4().hex[:12]}"
    criado = []
    criar_pool_original = repositorio._criar_pool

    def criar_pool(url):
        if not criado:
            with psycopg.connect(base, autocommit=True) as conexao:
                conexao.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema}"')
            criado.append(schema)
        return criar_pool_original(url)

    monkeypatch.setattr(repositorio, "_criar_pool", criar_pool)
    monkeypatch.setattr(settings, "database_url", _com_search_path(base, schema))
    yield schema

    repositorio.encerrar()
    if criado:
        with psycopg.connect(base, autocommit=True) as conexao:
            conexao.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
