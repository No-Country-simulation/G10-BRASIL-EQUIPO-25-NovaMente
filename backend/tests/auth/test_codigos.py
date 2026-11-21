"""Ciclo do código de 6 dígitos: emissão, validação, expiração e tentativas."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.auth import codigos
from app.models.db import CodigoLoginDB

EMAIL = "ana@exemplo.com"


@pytest.fixture
def relogio(monkeypatch, auth_ligada):
    agora = {"t": datetime(2026, 11, 21, 12, 0, tzinfo=timezone.utc)}
    monkeypatch.setattr(codigos, "_agora", lambda: agora["t"])
    return agora


def _linhas(db):
    db.expire_all()
    return db.scalars(select(CodigoLoginDB).order_by(CodigoLoginDB.id)).all()


def _errado(codigo: str) -> str:
    return f"{(int(codigo) + 1) % 10**6:06d}"


def test_codigo_tem_6_digitos_com_zeros_a_esquerda(monkeypatch):
    monkeypatch.setattr(codigos.secrets, "randbelow", lambda _limite: 42)
    assert codigos.novo_codigo() == "000042"


def test_codigo_valido_e_de_uso_unico(db_session, relogio):
    codigo = codigos.emitir(db_session, "aluno", "login", EMAIL)
    assert len(codigo) == 6 and codigo.isdigit()
    assert codigos.validar(db_session, "aluno", "login", EMAIL, codigo)
    assert not codigos.validar(db_session, "aluno", "login", EMAIL, codigo)
    (linha,) = _linhas(db_session)
    assert linha.usado_em is not None


def test_banco_guarda_so_o_hash(db_session, relogio):
    codigo = codigos.emitir(db_session, "aluno", "login", "  Ana@Exemplo.COM ")
    (linha,) = _linhas(db_session)
    assert linha.email == EMAIL
    assert codigo not in linha.codigo_hash
    assert linha.codigo_hash == codigos.hash_do_codigo(EMAIL, "aluno", "login", codigo)
    assert len(linha.codigo_hash) == 64
    assert linha.tentativas == 0 and linha.usado_em is None
    criado = datetime.fromisoformat(linha.criado_em)
    assert datetime.fromisoformat(linha.expira_em) - criado == timedelta(minutes=10)


def test_codigo_expira_em_10_minutos(db_session, relogio):
    codigo = codigos.emitir(db_session, "aluno", "login", EMAIL)
    relogio["t"] += timedelta(minutes=10)
    assert not codigos.validar(db_session, "aluno", "login", EMAIL, codigo)


def test_ainda_vale_antes_dos_10_minutos(db_session, relogio):
    codigo = codigos.emitir(db_session, "aluno", "login", EMAIL)
    relogio["t"] += timedelta(minutes=9, seconds=59)
    assert codigos.validar(db_session, "aluno", "login", EMAIL, codigo)


def test_cinco_erros_invalidam_o_codigo(db_session, relogio):
    codigo = codigos.emitir(db_session, "aluno", "login", EMAIL)
    for _ in range(4):
        assert not codigos.validar(db_session, "aluno", "login", EMAIL, _errado(codigo))
    assert _linhas(db_session)[0].tentativas == 4
    assert codigos.validar(db_session, "aluno", "login", EMAIL, codigo)  # 4 erros ainda deixam passar

    codigo = codigos.emitir(db_session, "aluno", "login", EMAIL)
    for _ in range(5):
        assert not codigos.validar(db_session, "aluno", "login", EMAIL, _errado(codigo))
    assert not codigos.validar(db_session, "aluno", "login", EMAIL, codigo)


def test_reemissao_invalida_o_anterior(db_session, relogio):
    primeiro = codigos.emitir(db_session, "aluno", "login", EMAIL)
    segundo = codigos.emitir(db_session, "aluno", "login", EMAIL)
    if primeiro != segundo:
        assert not codigos.validar(db_session, "aluno", "login", EMAIL, primeiro)
    assert len(_linhas(db_session)) == 1
    assert codigos.validar(db_session, "aluno", "login", EMAIL, segundo)


def test_codigo_preso_ao_perfil_e_ao_proposito(db_session, relogio):
    codigo = codigos.emitir(db_session, "aluno", "senha", EMAIL)
    outro_perfil = codigos.emitir(db_session, "empresa", "senha", EMAIL)
    assert len(_linhas(db_session)) == 2  # perfis diferentes não se anulam
    assert not codigos.validar(db_session, "aluno", "login", EMAIL, codigo)
    assert not codigos.validar(db_session, "empresa", "senha", EMAIL, codigo) or codigo == outro_perfil
    assert not codigos.validar(db_session, "aluno", "senha", "outro@exemplo.com", codigo)
    assert codigos.validar(db_session, "aluno", "senha", EMAIL, codigo)


def test_emitir_apaga_os_expirados_ha_mais_de_um_dia(db_session, relogio):
    codigos.emitir(db_session, "aluno", "login", "velho@exemplo.com")
    codigos.emitir(db_session, "aluno", "login", "recente@exemplo.com")
    relogio["t"] += timedelta(days=1, minutes=5)
    codigos.emitir(db_session, "aluno", "login", "recente2@exemplo.com")
    # Os dois primeiros expiraram há 1 dia e 5 min - 10 min: menos de um dia, ficam.
    assert len(_linhas(db_session)) == 3
    relogio["t"] += timedelta(minutes=10)
    codigos.emitir(db_session, "aluno", "login", EMAIL)
    assert {linha.email for linha in _linhas(db_session)} == {"recente2@exemplo.com", EMAIL}


def test_invalidar_pendentes_do_aluno(db_session, relogio):
    login = codigos.emitir(db_session, "aluno", "login", EMAIL)
    senha = codigos.emitir(db_session, "aluno", "senha", EMAIL)
    codigos.invalidar_pendentes(db_session, "aluno", EMAIL)
    assert not codigos.validar(db_session, "aluno", "login", EMAIL, login)
    assert not codigos.validar(db_session, "aluno", "senha", EMAIL, senha)
