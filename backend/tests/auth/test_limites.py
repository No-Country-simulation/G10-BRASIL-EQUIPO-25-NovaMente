"""Limites do login: consulta sem contar e Retry-After."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.auth import limites
from app.core.limite_taxa import LimiteDeTaxa


def test_espera_consulta_sem_contar():
    agora = {"t": 0.0}
    limite = LimiteDeTaxa(2, janela_segundos=100, relogio=lambda: agora["t"])
    assert limite.espera("k") is None
    assert len(limite) == 0  # consultar não cria a chave
    limite.registrar("k")
    agora["t"] = 10
    limite.registrar("k")
    assert limite.espera("k") == pytest.approx(90)
    assert limite.espera("k") == pytest.approx(90)  # continua sem contar
    agora["t"] = 100
    assert limite.espera("k") is None  # a primeira saiu da janela
    assert limite.registrar("k") is None


def _status_e_retry(funcao, *args):
    with pytest.raises(HTTPException) as erro:
        funcao(*args)
    return erro.value.status_code, erro.value.detail["erro"]["codigo"], erro.value.headers["Retry-After"]


def test_tres_envios_por_email(monkeypatch):
    agora = {"t": 1000.0}
    for limite in limites.TODOS:
        monkeypatch.setattr(limite, "relogio", lambda: agora["t"])
    for i in range(3):
        limites.consumir_envio("aluno", "ana@exemplo.com", f"10.0.0.{i}")
    agora["t"] += 0.4
    assert _status_e_retry(limites.consumir_envio, "aluno", "ana@exemplo.com", "10.0.0.9") == (
        429, "AUTH_LIMITE_EXCEDIDO", "600",
    )
    # Barrado não conta: o IP novo continua com a cota inteira para outro e-mail.
    limites.consumir_envio("aluno", "bia@exemplo.com", "10.0.0.9")


def test_dez_envios_por_ip():
    for i in range(10):
        limites.consumir_envio("aluno", f"a{i}@exemplo.com", "10.0.0.1")
    assert _status_e_retry(limites.consumir_envio, "aluno", "novo@exemplo.com", "10.0.0.1")[:2] == (
        429, "AUTH_LIMITE_EXCEDIDO",
    )


def test_falhas_de_senha_contam_so_quando_registradas():
    for _ in range(9):
        limites.contar_falha_de_senha("empresa", "e@x.com", "10.0.0.1")
    limites.barrar_falhas_de_senha("empresa", "e@x.com", "10.0.0.1")  # 9 ainda passa
    limites.contar_falha_de_senha("empresa", "e@x.com", "10.0.0.1")
    codigo, retry = _status_e_retry(limites.barrar_falhas_de_senha, "empresa", "e@x.com", "10.0.0.2")[1:]
    assert codigo == "AUTH_LIMITE_EXCEDIDO" and 1 <= int(retry) <= 900
    limites.barrar_falhas_de_senha("aluno", "e@x.com", "10.0.0.2")  # perfil separado


def test_trinta_falhas_por_ip():
    for i in range(30):
        limites.contar_falha_de_senha("aluno", f"a{i}@x.com", "10.0.0.1")
    with pytest.raises(HTTPException):
        limites.barrar_falhas_de_senha("aluno", "novo@x.com", "10.0.0.1")


def test_trinta_verificacoes_por_ip():
    for _ in range(30):
        limites.consumir_verificacao("10.0.0.1")
    with pytest.raises(HTTPException) as erro:
        limites.consumir_verificacao("10.0.0.1")
    assert erro.value.status_code == 429 and int(erro.value.headers["Retry-After"]) >= 1
    limites.consumir_verificacao("10.0.0.2")
