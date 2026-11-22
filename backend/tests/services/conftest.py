"""Fixtures dos testes de serviços: embedding falso e Chroma temporário."""

import chromadb
import pytest

from app.rag import armazenamento, embeddings
from tests.rag.falsos import EmbeddingFalso


@pytest.fixture
def embedding_falso():
    falso = EmbeddingFalso()
    embeddings.definir_embeddings(falso)
    yield falso
    embeddings.definir_embeddings(None)


@pytest.fixture
def chroma_temporario(tmp_path, monkeypatch):
    pasta = tmp_path / "chroma"
    monkeypatch.setenv("CHROMA_DIR", str(pasta))
    armazenamento.definir_cliente(chromadb.PersistentClient(path=str(pasta)))
    yield
    armazenamento.definir_cliente(None)
