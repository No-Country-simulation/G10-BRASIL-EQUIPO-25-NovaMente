"""Configuração do pytest para o backend."""

import os
import sys
import tempfile
from datetime import datetime, timezone

# Adiciona o diretório backend ao path para que os imports funcionem
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Aponta o banco para um arquivo temporário antes de importar a aplicação.
_TMP = tempfile.mkdtemp(prefix="novamente-tests-")
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP}/test.db"

import pytest  # noqa: E402
from sqlalchemy import text  # noqa: E402
from ulid import ULID  # noqa: E402

from app.models import (  # noqa: E402
    AdaptacaoPacote,
    ArmazenamentoOci,
    AvaliacaoQualidade,
    ConteudoFlashcards,
    DocumentoRef,
    FlashcardItem,
    MetadadosAdaptacao,
)
from app.models.db import MaterialDB  # noqa: E402


def _pacote_exemplo(adaptacao_id: str | None = None) -> AdaptacaoPacote:
    """Pacote completo e válido reaproveitado pelas fixtures."""
    return AdaptacaoPacote(
        adaptacao_id=adaptacao_id or str(ULID()),
        criado_em="2026-11-09T12:00:00+00:00",
        documento=DocumentoRef(titulo="Manual de Redes", origem="texto"),
        metadados=MetadadosAdaptacao(
            perfil_aplicado="Iniciante",
            formato_gerado="Flashcards",
            nivel_detalhe_aplicado="Didatico",
            nicho_setor_aplicado="Geral",
            tempo_estimado_estudo_minutos=10,
            conceitos_chave=["VCN", "Subnet", "Roteamento"],
        ),
        conteudo_adaptado=ConteudoFlashcards(
            titulo="Fundamentos de VCN",
            introducao_contextualizada="Revisão rápida dos conceitos de rede virtual.",
            itens=[
                FlashcardItem(
                    frente="O que é uma VCN?",
                    verso="Uma rede virtual privada na nuvem.",
                    dica_didatica="Pense em um condomínio fechado.",
                ),
                FlashcardItem(
                    frente="O que é uma subnet?",
                    verso="Uma subdivisão da VCN.",
                ),
                FlashcardItem(
                    frente="Para que serve o roteamento?",
                    verso="Direcionar o tráfego entre subnets.",
                    dica_didatica="Como o GPS da rede.",
                ),
            ],
        ),
        avaliacao_qualidade=AvaliacaoQualidade(
            ancoragem_fonte_score=0.91,
            clareza_pedagogica="Alta",
        ),
        armazenamento_oci=ArmazenamentoOci(
            bucket="bucket-teste",
            objeto_id="novamente-teste.json",
            status_upload="concluido",
        ),
    )


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


@pytest.fixture
def pacote_exemplo():
    """Pacote de adaptação completo para testes de persistência."""
    return _pacote_exemplo()


@pytest.fixture
def semear_material(db_session):
    """Grava um material no banco e devolve o ``material_id``."""

    def _semear(visibilidade: str = "rascunho", **campos) -> str:
        agora = datetime.now(timezone.utc).isoformat()
        adaptacao_id = campos.get("adaptacao_id") or str(ULID())
        valores = {
            "material_id": adaptacao_id,
            "adaptacao_id": adaptacao_id,
            "titulo": "Material de teste",
            "documento_titulo": "Documento de teste",
            "documento_origem": "texto",
            "documento_nome_arquivo": None,
            "documento_tamanho_bytes": None,
            "perfil": "Iniciante",
            "formato": "Flashcards",
            "nivel": "Didatico",
            "nicho": "Geral",
            "tempo_estimado_minutos": 10,
            "ancoragem_score": 0.9,
            "status_upload": "concluido",
            "conceitos_chave_json": '["VCN"]',
            "oci_objeto_id": "objeto-teste.json",
            "visibilidade": visibilidade,
            "pacote_json": _pacote_exemplo(adaptacao_id).model_dump_json(),
            "owner_id": None,
            "criado_em": agora,
            "atualizado_em": agora,
        }
        valores.update(campos)
        db_session.add(MaterialDB(**valores))
        db_session.commit()
        return valores["material_id"]

    return _semear
