import sys
from pathlib import Path

# Permite importar `app.rag` rodando o pytest a partir da raiz do repositório.
BACKEND = Path(__file__).resolve().parents[2]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import chromadb  # noqa: E402
import pytest  # noqa: E402

from app.rag import armazenamento, embeddings  # noqa: E402
from tests.rag.falsos import EmbeddingFalso  # noqa: E402


@pytest.fixture
def embedding_falso():
    falso = EmbeddingFalso()
    embeddings.definir_embeddings(falso)
    yield falso
    embeddings.definir_embeddings(None)


@pytest.fixture
def chroma_temporario(tmp_path):
    armazenamento.definir_cliente(chromadb.PersistentClient(path=str(tmp_path / "chroma")))
    yield
    armazenamento.definir_cliente(None)
