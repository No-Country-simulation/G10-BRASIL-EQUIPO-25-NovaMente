"""Testes da base SQLite e dos modelos ORM."""

from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.db import AlunoDB, MaterialDB, VinculoDB


def agora():
    return datetime.now(timezone.utc).isoformat()


def test_email_unico_ignora_caixa(db_session):
    db_session.add(
        AlunoDB(
            aluno_id="A1",
            nome="Ana",
            email="ana@exemplo.com",
            status="ativo",
            criado_em=agora(),
            atualizado_em=agora(),
        )
    )
    db_session.commit()
    db_session.add(
        AlunoDB(
            aluno_id="A2",
            nome="Bia",
            email="ANA@exemplo.com",
            status="ativo",
            criado_em=agora(),
            atualizado_em=agora(),
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_excluir_aluno_remove_vinculos(db_session):
    aluno = AlunoDB(
        aluno_id="A1",
        nome="Ana",
        email="ana@exemplo.com",
        status="ativo",
        criado_em=agora(),
        atualizado_em=agora(),
    )
    material = MaterialDB(
        material_id="M1",
        adaptacao_id="M1",
        titulo="Material de VCN",
        documento_titulo="Documento de VCN",
        documento_origem="texto",
        documento_nome_arquivo=None,
        documento_tamanho_bytes=None,
        perfil="Iniciante",
        formato="Flashcards",
        nivel="Didatico",
        nicho="Geral",
        tempo_estimado_minutos=10,
        ancoragem_score=0.9,
        status_upload="concluido",
        conceitos_chave_json='["VCN"]',
        oci_objeto_id="obj-1",
        visibilidade="rascunho",
        pacote_json="{}",
        criado_em=agora(),
        atualizado_em=agora(),
    )
    vinculo = VinculoDB(
        aluno_id="A1",
        material_id="M1",
        criado_em=agora(),
    )
    db_session.add_all([aluno, material, vinculo])
    db_session.commit()

    db_session.delete(aluno)
    db_session.commit()

    assert db_session.scalar(select(VinculoDB).where(VinculoDB.aluno_id == "A1")) is None
    assert db_session.get(MaterialDB, "M1") is not None
