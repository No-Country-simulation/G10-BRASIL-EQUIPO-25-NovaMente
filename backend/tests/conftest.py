"""Configuração do pytest para o backend."""

import os
import sys
import tempfile

# Adiciona o diretório backend ao path para que os imports funcionem
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Aponta o banco para um arquivo temporário antes de importar a aplicação.
_TMP = tempfile.mkdtemp(prefix="novamente-tests-")
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP}/test.db"

import pytest  # noqa: E402
from sqlalchemy import text  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _schema():
    import app.models.db  # noqa: F401  # registra as tabelas no metadata
    from app.core.db import Base, engine

    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture(autouse=True)
def _limpar(_schema):
    from app.core.db import engine

    with engine.begin() as conn:
        conn.execute(text("DELETE FROM vinculos"))
        conn.execute(text("DELETE FROM materiais"))
        conn.execute(text("DELETE FROM alunos"))


@pytest.fixture
def db_session(_schema):
    from app.core.db import SessionLocal

    with SessionLocal() as session:
        yield session


@pytest.fixture
def cliente(db_session):
    from fastapi.testclient import TestClient

    from app.core.db import get_db
    from app.main import app

    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
