"""Fixtures do login: configuração ligada, enviador falso e alunos com senha."""

from __future__ import annotations

import pytest
from pydantic import SecretStr
from sqlalchemy import text

from app.auth import limites
from app.auth.email import obter_enviador
from tests.auth.apoio import (
    EMPRESA_EMAIL,
    SEGREDO_TESTE,
    SENHA_ALUNO,
    SENHA_EMPRESA,
    EnviadorFalso,
    hash_de,
)


@pytest.fixture(autouse=True)
def _estado_limpo(_schema):
    """Limites em memória e códigos gravados não passam de um teste para outro."""
    from app.core.db import engine

    limites.limpar()
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM codigos_login"))
    yield
    limites.limpar()


@pytest.fixture
def auth_ligada(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "auth_habilitada", True)
    monkeypatch.setattr(settings, "demo_habilitado", False)
    monkeypatch.setattr(settings, "sessao_segredo", SecretStr(SEGREDO_TESTE))
    monkeypatch.setattr(settings, "sessao_cookie_seguro", False)
    monkeypatch.setattr(settings, "empresa_email", EMPRESA_EMAIL)
    monkeypatch.setattr(settings, "empresa_senha_hash", SecretStr(hash_de(SENHA_EMPRESA)))
    monkeypatch.setattr(settings, "email_modo", "console")
    return settings


@pytest.fixture
def enviador(cliente):
    from app.main import app

    falso = EnviadorFalso()
    app.dependency_overrides[obter_enviador] = lambda: falso
    return falso


@pytest.fixture
def aluno_com_senha(semear_aluno):
    """Aluno ativo (ou com os campos dados) com senha; devolve (aluno_id, email)."""

    def _criar(email: str = "ana@exemplo.com", senha: str | None = SENHA_ALUNO, **campos):
        aluno_id = semear_aluno(email=email, senha_hash=hash_de(senha) if senha else None, **campos)
        return aluno_id, email

    return _criar
