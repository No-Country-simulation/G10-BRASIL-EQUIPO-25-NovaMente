"""Erros de código por e-mail: 10 a cada 15 min, sem zerar quando o código é reemitido."""

from __future__ import annotations

import pytest

from app.auth import limites
from tests.auth.apoio import EMPRESA_EMAIL, SENHA_ALUNO, SENHA_EMPRESA

API = "/api/v1/auth"
SENHA_NOVA = "Nova$enha9"


def _errado(codigo: str) -> str:
    return f"{(int(codigo) + 1) % 10**6:06d}"


def _verificar(cliente, rota, email, codigo, **extra):
    return cliente.post(f"{API}{rota}", json={"email": email, "codigo": codigo, **extra})


def _assert_429(resposta):
    assert resposta.status_code == 429
    assert resposta.json()["erro"]["codigo"] == "AUTH_LIMITE_EXCEDIDO"
    assert 1 <= int(resposta.headers["Retry-After"]) <= 900


def test_dez_erros_bloqueiam_mesmo_com_codigo_novo(cliente, auth_ligada, enviador, aluno_com_senha):
    _, email = aluno_com_senha()
    for rodada in range(2):  # 5 erros por código, com reemissão no meio
        cliente.post(f"{API}/aluno/login", json={"email": email, "senha": SENHA_ALUNO})
        for _ in range(5):
            r = _verificar(cliente, "/aluno/verificar", email, _errado(enviador.ultimo_codigo))
            assert r.status_code == 401
    # Código novo e certo: ainda assim barrado, sem consumir o código.
    assert cliente.post(f"{API}/aluno/login", json={"email": email, "senha": SENHA_ALUNO}).status_code == 202
    codigo = enviador.ultimo_codigo
    _assert_429(_verificar(cliente, "/aluno/verificar", email, codigo))
    limites.limpar()
    assert _verificar(cliente, "/aluno/verificar", email, codigo).status_code == 200


def test_definir_senha_compartilha_o_limite_do_aluno(cliente, auth_ligada, enviador, aluno_com_senha):
    _, email = aluno_com_senha(senha=None)
    for _ in range(2):
        cliente.post(f"{API}/aluno/senha/codigo", json={"email": email})
        for _ in range(5):
            r = _verificar(cliente, "/aluno/senha/definir", email, _errado(enviador.ultimo_codigo), senha=SENHA_NOVA)
            assert r.status_code == 401
    limites.envio_por_email.limpar()
    cliente.post(f"{API}/aluno/senha/codigo", json={"email": email})
    _assert_429(_verificar(cliente, "/aluno/senha/definir", email, enviador.ultimo_codigo, senha=SENHA_NOVA))
    # A política continua antes de tudo: senha fraca dá 422 mesmo bloqueado.
    fraca = _verificar(cliente, "/aluno/senha/definir", email, enviador.ultimo_codigo, senha="fraca")
    assert fraca.status_code == 422 and fraca.json()["erro"]["codigo"] == "SENHA_FRACA"


def test_senha_fraca_nao_consome_o_limite(cliente, auth_ligada, enviador, aluno_com_senha):
    _, email = aluno_com_senha(senha=None)
    cliente.post(f"{API}/aluno/senha/codigo", json={"email": email})
    for _ in range(15):
        assert _verificar(cliente, "/aluno/senha/definir", email, "000000", senha="fraca").status_code == 422
    r = _verificar(cliente, "/aluno/senha/definir", email, enviador.ultimo_codigo, senha=SENHA_NOVA)
    assert r.status_code == 200


@pytest.mark.parametrize("rota,extra", [("/aluno/verificar", {}), ("/aluno/senha/definir", {"senha": SENHA_NOVA})])
def test_email_desconhecido_bloqueia_do_mesmo_jeito(cliente, auth_ligada, aluno_com_senha, rota, extra):
    _, conhecido = aluno_com_senha()
    respostas = {}
    for email in (conhecido, "ninguem@exemplo.com"):
        for _ in range(10):
            assert _verificar(cliente, rota, email, "123456", **extra).status_code == 401
        respostas[email] = _verificar(cliente, rota, email, "123456", **extra)
    for r in respostas.values():
        _assert_429(r)
    a, b = respostas.values()
    assert a.json() == b.json()


def test_empresa_com_email_errado_conta_e_bloqueia(cliente, auth_ligada, enviador):
    for _ in range(10):
        assert _verificar(cliente, "/empresa/verificar", "outra@exemplo.com", "123456").status_code == 401
    _assert_429(_verificar(cliente, "/empresa/verificar", "outra@exemplo.com", "123456"))
    # Outro e-mail tem o próprio limite: a empresa ainda entra.
    cliente.post(f"{API}/empresa/login", json={"email": EMPRESA_EMAIL, "senha": SENHA_EMPRESA})
    assert _verificar(cliente, "/empresa/verificar", EMPRESA_EMAIL, enviador.ultimo_codigo).status_code == 200


def test_codigo_certo_dentro_do_limite_entra(cliente, auth_ligada, enviador):
    cliente.post(f"{API}/empresa/login", json={"email": EMPRESA_EMAIL, "senha": SENHA_EMPRESA})
    codigo = enviador.ultimo_codigo
    for _ in range(4):
        assert _verificar(cliente, "/empresa/verificar", EMPRESA_EMAIL, _errado(codigo)).status_code == 401
    cliente.post(f"{API}/empresa/login", json={"email": EMPRESA_EMAIL, "senha": SENHA_EMPRESA})
    codigo = enviador.ultimo_codigo
    for _ in range(5):
        assert _verificar(cliente, "/empresa/verificar", EMPRESA_EMAIL, _errado(codigo)).status_code == 401
    # 9 erros: o décimo pedido ainda passa pela barreira, mas o código já morreu (5 erros).
    cliente.post(f"{API}/empresa/login", json={"email": EMPRESA_EMAIL, "senha": SENHA_EMPRESA})
    assert _verificar(cliente, "/empresa/verificar", EMPRESA_EMAIL, enviador.ultimo_codigo).status_code == 200


def test_aluno_desativado_depois_do_codigo_conta_como_erro(
    cliente, auth_ligada, enviador, aluno_com_senha, db_session
):
    from app.models.db import AlunoDB

    aluno_id, email = aluno_com_senha()
    for _ in range(10):
        cliente.post(f"{API}/aluno/login", json={"email": email, "senha": SENHA_ALUNO})
        db_session.get(AlunoDB, aluno_id).status = "inativo"
        db_session.commit()
        assert _verificar(cliente, "/aluno/verificar", email, enviador.ultimo_codigo).status_code == 401
        db_session.get(AlunoDB, aluno_id).status = "ativo"
        db_session.commit()
        limites.envio_por_email.limpar()
    assert limites.falha_de_codigo_por_email.espera(f"aluno:{email}") is not None


def test_limpar_zera_o_limite_de_codigo():
    assert limites.falha_de_codigo_por_email in limites.TODOS
    for _ in range(10):
        limites.contar_falha_de_codigo("aluno", "a@exemplo.com")
    with pytest.raises(Exception):
        limites.barrar_falhas_de_codigo("aluno", "a@exemplo.com")
    limites.limpar()
    limites.barrar_falhas_de_codigo("aluno", "a@exemplo.com")
