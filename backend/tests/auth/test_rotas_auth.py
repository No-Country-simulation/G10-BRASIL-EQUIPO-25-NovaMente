"""Rotas /api/v1/auth com o enviador falso (nenhum e-mail sai de verdade)."""

from __future__ import annotations

import logging

import pytest
from sqlalchemy import select

from app.models.db import AlunoDB, CodigoLoginDB
from tests.auth.apoio import (
    EMPRESA_EMAIL,
    SENHA_ALUNO,
    SENHA_EMPRESA,
    entrar_aluno,
    entrar_empresa,
)

API = "/api/v1/auth"
SENHA_NOVA = "Nova$enha9"
ROTAS_LIGADAS = [
    ("get", "/eu", None),
    ("post", "/sair", None),
    ("post", "/empresa/login", {"email": EMPRESA_EMAIL, "senha": SENHA_EMPRESA}),
    ("post", "/empresa/verificar", {"email": EMPRESA_EMAIL, "codigo": "123456"}),
    ("post", "/aluno/login", {"email": "a@exemplo.com", "senha": "x"}),
    ("post", "/aluno/verificar", {"email": "a@exemplo.com", "codigo": "123456"}),
    ("post", "/aluno/senha/codigo", {"email": "a@exemplo.com"}),
    ("post", "/aluno/senha/definir", {"email": "a@exemplo.com", "codigo": "123456", "senha": SENHA_NOVA}),
    ("post", "/demo", {"perfil": "empresa"}),
]


def _pedir(cliente, metodo, rota, corpo):
    return getattr(cliente, metodo)(API + rota, **({"json": corpo} if corpo is not None else {}))


def _errado(codigo: str) -> str:
    return f"{(int(codigo) + 1) % 10**6:06d}"


# ── Login desligado ───────────────────────────────────────────────────────────


def test_config_e_publica_e_desligada_por_padrao(cliente):
    assert cliente.get(f"{API}/config").json() == {"auth_habilitada": False, "demo_habilitado": False}


@pytest.mark.parametrize("metodo,rota,corpo", ROTAS_LIGADAS)
def test_desligado_as_demais_rotas_respondem_404(cliente, metodo, rota, corpo):
    resposta = _pedir(cliente, metodo, rota, corpo)
    assert resposta.status_code == 404
    assert resposta.json() == cliente.get("/api/v1/rota-que-nao-existe").json()


def test_desligado_as_rotas_antigas_seguem_abertas(cliente, semear_aluno):
    aluno = semear_aluno()
    assert cliente.get("/api/v1/alunos").status_code == 200
    assert cliente.get("/api/v1/aluno/identificacao").status_code == 200
    assert cliente.get(f"/api/v1/aluno/materiais?aluno_id={aluno}").status_code == 200
    sem_id = cliente.get("/api/v1/aluno/materiais")
    assert sem_id.status_code == 422 and "aluno_id" in sem_id.json()["erro"]["campos"]


def test_config_ligada(cliente, auth_ligada, monkeypatch):
    monkeypatch.setattr(auth_ligada, "demo_habilitado", True)
    assert cliente.get(f"{API}/config").json() == {"auth_habilitada": True, "demo_habilitado": True}


# ── Empresa ───────────────────────────────────────────────────────────────────


def test_fluxo_completo_da_empresa(cliente, auth_ligada, enviador):
    assert cliente.get(f"{API}/eu").status_code == 401

    r = cliente.post(f"{API}/empresa/login", json={"email": "  Empresa@Exemplo.COM ", "senha": SENHA_EMPRESA})
    assert r.status_code == 202
    assert r.json() == {"mensagem": "Enviamos um código de 6 dígitos para o seu e-mail.", "expira_em_segundos": 600}
    ((destino, codigo),) = enviador.enviados
    assert destino == EMPRESA_EMAIL and len(codigo) == 6
    assert "nm_sessao" not in cliente.cookies  # a senha sozinha não abre sessão

    r = cliente.post(f"{API}/empresa/verificar", json={"email": "EMPRESA@exemplo.com", "codigo": codigo})
    assert r.status_code == 200
    assert r.json() == {"tipo": "empresa", "email": EMPRESA_EMAIL}
    assert "nm_sessao" in cliente.cookies

    assert cliente.get(f"{API}/eu").json() == {"tipo": "empresa", "email": EMPRESA_EMAIL}
    assert cliente.get("/api/v1/alunos").status_code == 200

    r = cliente.post(f"{API}/sair")
    assert r.status_code == 204 and "nm_sessao" not in cliente.cookies
    assert cliente.get(f"{API}/eu").status_code == 401
    assert cliente.get("/api/v1/alunos").status_code == 401


def test_empresa_email_ou_senha_errados_dao_a_mesma_resposta(cliente, auth_ligada, enviador):
    errado_email = cliente.post(f"{API}/empresa/login", json={"email": "outra@exemplo.com", "senha": SENHA_EMPRESA})
    errada_senha = cliente.post(f"{API}/empresa/login", json={"email": EMPRESA_EMAIL, "senha": "Errada@123"})
    assert errado_email.status_code == errada_senha.status_code == 401
    assert errado_email.json() == errada_senha.json() == {
        "erro": {"codigo": "CREDENCIAIS_INVALIDAS", "mensagem": "E-mail ou senha incorretos."}
    }
    assert enviador.enviados == []


def test_empresa_codigo_errado(cliente, auth_ligada, enviador):
    cliente.post(f"{API}/empresa/login", json={"email": EMPRESA_EMAIL, "senha": SENHA_EMPRESA})
    r = cliente.post(f"{API}/empresa/verificar", json={"email": EMPRESA_EMAIL, "codigo": _errado(enviador.ultimo_codigo)})
    assert r.status_code == 401
    assert r.json() == {"erro": {"codigo": "CODIGO_INVALIDO", "mensagem": "Código inválido ou vencido."}}
    assert "nm_sessao" not in cliente.cookies


def test_falha_de_envio_no_login_da_503(cliente, auth_ligada, enviador, caplog):
    enviador.falhar = True
    r = cliente.post(f"{API}/empresa/login", json={"email": EMPRESA_EMAIL, "senha": SENHA_EMPRESA})
    assert r.status_code == 503
    assert r.json()["erro"]["codigo"] == "EMAIL_INDISPONIVEL"


# ── Aluno ─────────────────────────────────────────────────────────────────────


def test_fluxo_completo_do_aluno(cliente, auth_ligada, enviador, aluno_com_senha):
    aluno_id, email = aluno_com_senha(nome="Ana Souza")
    r = cliente.post(f"{API}/aluno/login", json={"email": email.upper(), "senha": SENHA_ALUNO})
    assert r.status_code == 202
    assert enviador.enviados[-1][0] == email
    r = cliente.post(f"{API}/aluno/verificar", json={"email": email, "codigo": enviador.ultimo_codigo})
    assert r.status_code == 200
    assert r.json() == {"tipo": "aluno", "aluno_id": aluno_id, "nome": "Ana Souza"}
    assert cliente.get(f"{API}/eu").json() == {"tipo": "aluno", "aluno_id": aluno_id, "nome": "Ana Souza"}
    assert cliente.get("/api/v1/aluno/materiais").status_code == 200
    assert cliente.post(f"{API}/sair").status_code == 204
    assert cliente.get(f"{API}/eu").status_code == 401


def test_aluno_desativado_perde_a_sessao(cliente, auth_ligada, enviador, aluno_com_senha, db_session):
    aluno_id, email = aluno_com_senha()
    entrar_aluno(cliente, enviador, email)
    db_session.get(AlunoDB, aluno_id).status = "inativo"
    db_session.commit()
    assert cliente.get(f"{API}/eu").json()["erro"]["codigo"] == "NAO_AUTENTICADO"
    assert cliente.get("/api/v1/aluno/materiais").status_code == 401


def test_aluno_apagado_perde_a_sessao(cliente, auth_ligada, enviador, aluno_com_senha, db_session):
    aluno_id, email = aluno_com_senha()
    entrar_aluno(cliente, enviador, email)
    db_session.delete(db_session.get(AlunoDB, aluno_id))
    db_session.commit()
    assert cliente.get("/api/v1/aluno/materiais").status_code == 401


def test_login_do_aluno_nao_revela_o_motivo(cliente, auth_ligada, enviador, aluno_com_senha):
    _, email = aluno_com_senha()
    aluno_com_senha("inativo@exemplo.com", status="inativo")
    aluno_com_senha("semsenha@exemplo.com", senha=None)
    respostas = [
        cliente.post(f"{API}/aluno/login", json={"email": email, "senha": "Errada@123"}),
        cliente.post(f"{API}/aluno/login", json={"email": "ninguem@exemplo.com", "senha": SENHA_ALUNO}),
        cliente.post(f"{API}/aluno/login", json={"email": "inativo@exemplo.com", "senha": SENHA_ALUNO}),
        cliente.post(f"{API}/aluno/login", json={"email": "semsenha@exemplo.com", "senha": SENHA_ALUNO}),
        cliente.post(f"{API}/aluno/login", json={"email": "nem-e-email", "senha": SENHA_ALUNO}),
    ]
    assert {r.status_code for r in respostas} == {401}
    assert {r.text for r in respostas} == {respostas[0].text}
    assert all(dict(r.headers).keys() == dict(respostas[0].headers).keys() for r in respostas)
    assert enviador.enviados == []


def test_codigo_de_login_nao_serve_para_outro_aluno(cliente, auth_ligada, enviador, aluno_com_senha):
    _, email = aluno_com_senha()
    aluno_com_senha("bia@exemplo.com")
    cliente.post(f"{API}/aluno/login", json={"email": email, "senha": SENHA_ALUNO})
    r = cliente.post(f"{API}/aluno/verificar", json={"email": "bia@exemplo.com", "codigo": enviador.ultimo_codigo})
    assert r.status_code == 401 and r.json()["erro"]["codigo"] == "CODIGO_INVALIDO"


def test_codigo_da_empresa_nao_abre_sessao_de_aluno(cliente, auth_ligada, enviador, aluno_com_senha):
    aluno_com_senha(EMPRESA_EMAIL)
    cliente.post(f"{API}/empresa/login", json={"email": EMPRESA_EMAIL, "senha": SENHA_EMPRESA})
    r = cliente.post(f"{API}/aluno/verificar", json={"email": EMPRESA_EMAIL, "codigo": enviador.ultimo_codigo})
    assert r.status_code == 401


# ── Primeiro acesso / esqueci a senha ─────────────────────────────────────────


def test_primeiro_acesso_completo(cliente, auth_ligada, enviador, aluno_com_senha, db_session):
    aluno_id, email = aluno_com_senha("novo@exemplo.com", senha=None, nome="Novo Aluno")

    r = cliente.post(f"{API}/aluno/senha/codigo", json={"email": " NOVO@exemplo.com"})
    assert r.status_code == 202
    assert r.json() == {
        "mensagem": "Se o e-mail estiver cadastrado, enviamos um código de 6 dígitos.",
        "expira_em_segundos": 600,
    }
    codigo = enviador.ultimo_codigo

    fraca = cliente.post(f"{API}/aluno/senha/definir", json={"email": email, "codigo": codigo, "senha": "fraca"})
    assert fraca.status_code == 422
    erro = fraca.json()["erro"]
    assert erro["codigo"] == "SENHA_FRACA"
    assert "uma letra maiúscula" in erro["campos"]["senha"] and "um número" in erro["campos"]["senha"]

    # O código não foi consumido pela senha fraca.
    r = cliente.post(f"{API}/aluno/senha/definir", json={"email": email, "codigo": codigo, "senha": SENHA_NOVA})
    assert r.status_code == 200
    assert r.json() == {"tipo": "aluno", "aluno_id": aluno_id, "nome": "Novo Aluno"}
    assert cliente.get(f"{API}/eu").json()["aluno_id"] == aluno_id

    db_session.expire_all()
    assert db_session.get(AlunoDB, aluno_id).senha_hash.startswith("scrypt$")
    assert db_session.scalars(select(CodigoLoginDB).where(CodigoLoginDB.usado_em.is_(None))).all() == []

    # Código usado não serve de novo; a senha nova entra pelo login normal.
    again = cliente.post(f"{API}/aluno/senha/definir", json={"email": email, "codigo": codigo, "senha": SENHA_NOVA})
    assert again.status_code == 401
    cliente.post(f"{API}/sair")
    entrar_aluno(cliente, enviador, email, SENHA_NOVA)
    assert cliente.post(f"{API}/aluno/login", json={"email": email, "senha": SENHA_ALUNO}).status_code == 401


def test_esqueci_a_senha_troca_a_senha(cliente, auth_ligada, enviador, aluno_com_senha):
    _, email = aluno_com_senha()
    cliente.post(f"{API}/aluno/senha/codigo", json={"email": email})
    r = cliente.post(
        f"{API}/aluno/senha/definir", json={"email": email, "codigo": enviador.ultimo_codigo, "senha": SENHA_NOVA}
    )
    assert r.status_code == 200
    assert cliente.post(f"{API}/aluno/login", json={"email": email, "senha": SENHA_ALUNO}).status_code == 401
    assert cliente.post(f"{API}/aluno/login", json={"email": email, "senha": SENHA_NOVA}).status_code == 202


def test_definir_com_codigo_errado(cliente, auth_ligada, enviador, aluno_com_senha):
    _, email = aluno_com_senha(senha=None)
    cliente.post(f"{API}/aluno/senha/codigo", json={"email": email})
    r = cliente.post(
        f"{API}/aluno/senha/definir",
        json={"email": email, "codigo": _errado(enviador.ultimo_codigo), "senha": SENHA_NOVA},
    )
    assert r.status_code == 401 and r.json()["erro"]["codigo"] == "CODIGO_INVALIDO"


def test_codigo_de_senha_nao_serve_para_login(cliente, auth_ligada, enviador, aluno_com_senha):
    _, email = aluno_com_senha()
    cliente.post(f"{API}/aluno/senha/codigo", json={"email": email})
    r = cliente.post(f"{API}/aluno/verificar", json={"email": email, "codigo": enviador.ultimo_codigo})
    assert r.status_code == 401


def test_pedido_de_codigo_igual_para_existente_e_inexistente(cliente, auth_ligada, enviador, aluno_com_senha):
    _, email = aluno_com_senha()
    aluno_com_senha("inativo@exemplo.com", status="inativo")
    existente = cliente.post(f"{API}/aluno/senha/codigo", json={"email": email})
    inexistente = cliente.post(f"{API}/aluno/senha/codigo", json={"email": "ninguem@exemplo.com"})
    inativo = cliente.post(f"{API}/aluno/senha/codigo", json={"email": "inativo@exemplo.com"})
    assert existente.status_code == inexistente.status_code == inativo.status_code == 202
    assert existente.text == inexistente.text == inativo.text
    assert [destino for destino, _ in enviador.enviados] == [email]


def test_falha_de_envio_no_pedido_de_codigo_nao_muda_a_resposta(
    cliente, auth_ligada, enviador, aluno_com_senha, caplog
):
    _, email = aluno_com_senha()
    enviador.falhar = True
    caplog.set_level(logging.ERROR)
    r = cliente.post(f"{API}/aluno/senha/codigo", json={"email": email})
    assert r.status_code == 202
    assert any("falha ao enviar o código" in rec.getMessage() for rec in caplog.records)


def test_limite_de_pedidos_de_codigo_vale_para_email_inexistente(cliente, auth_ligada, enviador):
    for _ in range(3):
        assert cliente.post(f"{API}/aluno/senha/codigo", json={"email": "ninguem@exemplo.com"}).status_code == 202
    r = cliente.post(f"{API}/aluno/senha/codigo", json={"email": "ninguem@exemplo.com"})
    assert r.status_code == 429
    assert r.json()["erro"]["codigo"] == "AUTH_LIMITE_EXCEDIDO"
    assert 1 <= int(r.headers["Retry-After"]) <= 600


def test_falhas_de_senha_bloqueiam_ate_a_senha_certa(cliente, auth_ligada, enviador):
    for _ in range(10):
        cliente.post(f"{API}/empresa/login", json={"email": EMPRESA_EMAIL, "senha": "Errada@123"})
    r = cliente.post(f"{API}/empresa/login", json={"email": EMPRESA_EMAIL, "senha": SENHA_EMPRESA})
    assert r.status_code == 429 and "Retry-After" in r.headers
    assert enviador.enviados == []


def test_codigo_nunca_vai_para_o_log_com_enviador_falso(cliente, auth_ligada, enviador, caplog):
    caplog.set_level(logging.DEBUG)
    cliente.post(f"{API}/empresa/login", json={"email": EMPRESA_EMAIL, "senha": SENHA_EMPRESA})
    texto = "\n".join(r.getMessage() for r in caplog.records)
    assert enviador.ultimo_codigo not in texto and SENHA_EMPRESA not in texto


# ── senha_hash nunca sai ──────────────────────────────────────────────────────


def test_senha_hash_nunca_aparece_nas_respostas(cliente, auth_ligada, enviador, aluno_com_senha, monkeypatch):
    aluno_id, email = aluno_com_senha()
    entrar_aluno(cliente, enviador, email)
    respostas = [cliente.get(f"{API}/eu"), cliente.get("/api/v1/aluno/materiais")]
    cliente.post(f"{API}/sair")
    entrar_empresa(cliente, enviador)
    respostas += [
        cliente.get("/api/v1/alunos"),
        cliente.get(f"/api/v1/alunos/{aluno_id}"),
        cliente.patch(f"/api/v1/alunos/{aluno_id}", json={"nome": "Ana Maria"}),
        cliente.post("/api/v1/alunos", json={"nome": "Carla", "email": "carla@exemplo.com"}),
        cliente.get("/openapi.json"),
    ]
    monkeypatch.setattr(auth_ligada, "auth_habilitada", False)
    respostas.append(cliente.get("/api/v1/aluno/identificacao"))
    for r in respostas:
        assert r.status_code < 300, r.text
        assert "senha_hash" not in r.text and "scrypt$" not in r.text


# ── Demonstração ──────────────────────────────────────────────────────────────


def test_demo_desligada_responde_404(cliente, auth_ligada):
    assert cliente.post(f"{API}/demo", json={"perfil": "empresa"}).status_code == 404


def test_demo_da_empresa(cliente, auth_ligada, monkeypatch):
    monkeypatch.setattr(auth_ligada, "demo_habilitado", True)
    r = cliente.post(f"{API}/demo", json={"perfil": "empresa"})
    assert r.status_code == 200
    assert r.json() == {"tipo": "empresa", "email": "demo@novamente.app", "demo": True}
    assert "Max-Age=7200" in r.headers["set-cookie"]
    assert cliente.get(f"{API}/eu").json() == {"tipo": "empresa", "email": "demo@novamente.app", "demo": True}
    assert cliente.get("/api/v1/alunos").status_code == 200


def test_demo_do_aluno_usa_o_primeiro_ativo_por_nome(cliente, auth_ligada, monkeypatch, semear_aluno):
    monkeypatch.setattr(auth_ligada, "demo_habilitado", True)
    assert cliente.post(f"{API}/demo", json={"perfil": "aluno"}).json()["erro"]["codigo"] == "ALUNO_NAO_ENCONTRADO"
    semear_aluno(nome="Zeca")
    semear_aluno(nome="Aaron Inativo", status="inativo")
    bruna = semear_aluno(nome="Bruna")
    r = cliente.post(f"{API}/demo", json={"perfil": "aluno"})
    assert r.json() == {"tipo": "aluno", "aluno_id": bruna, "nome": "Bruna", "demo": True}
    assert cliente.get(f"{API}/eu").json()["demo"] is True
    assert cliente.get("/api/v1/aluno/materiais").status_code == 200


def test_demo_perfil_invalido(cliente, auth_ligada, monkeypatch):
    monkeypatch.setattr(auth_ligada, "demo_habilitado", True)
    assert cliente.post(f"{API}/demo", json={"perfil": "admin"}).status_code == 422
