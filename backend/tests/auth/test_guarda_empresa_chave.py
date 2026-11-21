"""exigir_empresa com o login ligado: sessão de empresa ou X-API-Key."""

from __future__ import annotations

import pytest

from app.auth.sessao import NOME_COOKIE, criar_token
from app.core import seguranca
from app.core.config import settings
from tests.auth.apoio import EMPRESA_EMAIL

CHAVE = "chave-ficticia-de-teste-login"
NAO_AUTENTICADO = {"erro": {"codigo": "NAO_AUTENTICADO", "mensagem": "Entre para continuar."}}

# Rotas com a chave também sem login e rotas que, sem login, ficam abertas.
ROTAS = ["/api/v1/alunos", "/api/v1/materiais", "/api/v1/adaptacoes", "/api/v1/oci/status"]


@pytest.fixture
def com_chave(monkeypatch):
    monkeypatch.setattr(settings, "api_key_empresa", CHAVE)


def _entrar_como(cliente, tipo: str, sub: str) -> None:
    token, _ = criar_token(tipo, sub)
    cliente.cookies.set(NOME_COOKIE, token)


@pytest.mark.parametrize("rota", ROTAS)
def test_chave_certa_sem_sessao_passa(cliente, auth_ligada, com_chave, rota):
    r = cliente.get(rota, headers={"X-API-Key": CHAVE})
    assert r.status_code not in (401, 403)


@pytest.mark.parametrize("rota", ROTAS)
def test_sem_sessao_e_sem_chave_401(cliente, auth_ligada, com_chave, rota):
    r = cliente.get(rota)
    assert r.status_code == 401 and r.json() == NAO_AUTENTICADO


@pytest.mark.parametrize("enviada", ["chave-errada", CHAVE + "x", ""])
def test_chave_errada_401_sem_vazar_a_chave(cliente, auth_ligada, com_chave, enviada):
    r = cliente.get("/api/v1/alunos", headers={"X-API-Key": enviada})
    assert r.status_code == 401 and r.json() == NAO_AUTENTICADO
    assert CHAVE not in r.text


def test_sem_chave_configurada_o_cabecalho_nao_vale(cliente, auth_ligada, monkeypatch):
    monkeypatch.setattr(settings, "api_key_empresa", "  ")
    r = cliente.get("/api/v1/alunos", headers={"X-API-Key": "  "})
    assert r.status_code == 401 and r.json() == NAO_AUTENTICADO


def test_sessao_de_empresa_dispensa_a_chave(cliente, auth_ligada, com_chave):
    _entrar_como(cliente, "empresa", EMPRESA_EMAIL)
    assert cliente.get("/api/v1/alunos").status_code == 200


def test_sessao_de_aluno_sem_chave_403(cliente, auth_ligada, com_chave, semear_aluno):
    _entrar_como(cliente, "aluno", semear_aluno())
    r = cliente.get("/api/v1/alunos")
    assert r.status_code == 403 and r.json()["erro"]["codigo"] == "ACESSO_NEGADO"


def test_escrita_com_a_chave_chega_ao_dominio(cliente, auth_ligada, com_chave):
    r = cliente.delete("/api/v1/jobs/JOB_INEXISTENTE", headers={"X-API-Key": CHAVE})
    assert r.status_code == 404 and r.json()["erro"]["codigo"] == "JOB_NAO_ENCONTRADO"


def test_regra_da_chave_sem_login_nao_age_com_o_login_ligado(auth_ligada, com_chave):
    # Com o login ligado, quem decide é o exigir_empresa (sessão ou chave).
    assert seguranca.exigir_chave_empresa(None) is None
    assert seguranca.exigir_chave_empresa("chave-errada") is None


def test_chave_empresa_confere():
    assert seguranca.chave_empresa_confere(None) is False
