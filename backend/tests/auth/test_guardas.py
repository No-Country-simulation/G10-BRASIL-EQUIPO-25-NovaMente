"""Matriz de guardas com o login ligado: uma rota representativa de cada router."""

from __future__ import annotations

import pytest

from app.auth.sessao import NOME_COOKIE, criar_token
from tests.auth.apoio import EMPRESA_EMAIL

PERGUNTA = {"pergunta": "O que é uma VCN?"}

ROTAS_EMPRESA = [
    ("get", "/api/v1/adaptacoes", None),
    ("get", "/api/v1/jobs/JOB-QUALQUER", None),
    ("get", "/api/v1/materiais", None),
    ("get", "/api/v1/alunos", None),
    ("put", "/api/v1/alunos/ALUNO-X/materiais", {"material_ids": []}),
    ("get", "/api/v1/oci/status", None),
    ("post", "/api/v1/materiais/MAT-X/chat", PERGUNTA),
]
ROTAS_ALUNO = [
    ("get", "/api/v1/aluno/materiais?aluno_id=QUALQUER", None),
    ("get", "/api/v1/aluno/materiais/MAT-X?aluno_id=QUALQUER", None),
    ("post", "/api/v1/aluno/materiais/MAT-X/chat?aluno_id=QUALQUER", PERGUNTA),
]


def _pedir(cliente, metodo, rota, corpo=None):
    return getattr(cliente, metodo)(rota, **({"json": corpo} if corpo is not None else {}))


def _entrar_como(cliente, tipo: str, sub: str, **kw) -> None:
    token, _ = criar_token(tipo, sub, **kw)
    cliente.cookies.set(NOME_COOKIE, token)


@pytest.mark.parametrize("metodo,rota,corpo", ROTAS_EMPRESA + ROTAS_ALUNO + [("get", "/api/v1/chat/modelos", None)])
def test_sem_sessao_401(cliente, auth_ligada, metodo, rota, corpo):
    r = _pedir(cliente, metodo, rota, corpo)
    assert r.status_code == 401
    assert r.json() == {"erro": {"codigo": "NAO_AUTENTICADO", "mensagem": "Entre para continuar."}}


@pytest.mark.parametrize("metodo,rota,corpo", ROTAS_EMPRESA)
def test_sessao_de_aluno_em_rota_da_empresa_403(cliente, auth_ligada, semear_aluno, metodo, rota, corpo):
    _entrar_como(cliente, "aluno", semear_aluno())
    r = _pedir(cliente, metodo, rota, corpo)
    assert r.status_code == 403 and r.json()["erro"]["codigo"] == "ACESSO_NEGADO"


@pytest.mark.parametrize("metodo,rota,corpo", ROTAS_ALUNO)
def test_sessao_de_empresa_em_rota_do_aluno_403(cliente, auth_ligada, metodo, rota, corpo):
    _entrar_como(cliente, "empresa", EMPRESA_EMAIL)
    r = _pedir(cliente, metodo, rota, corpo)
    assert r.status_code == 403 and r.json()["erro"]["codigo"] == "ACESSO_NEGADO"


@pytest.mark.parametrize("metodo,rota,corpo", ROTAS_EMPRESA)
def test_sessao_de_empresa_passa_pela_guarda(cliente, auth_ligada, metodo, rota, corpo):
    _entrar_como(cliente, "empresa", EMPRESA_EMAIL)
    assert _pedir(cliente, metodo, rota, corpo).status_code not in (401, 403)


@pytest.mark.parametrize("tipo", ["empresa", "aluno"])
def test_modelos_do_chat_aceitam_os_dois_perfis(cliente, auth_ligada, semear_aluno, tipo):
    _entrar_como(cliente, tipo, EMPRESA_EMAIL if tipo == "empresa" else semear_aluno())
    assert cliente.get("/api/v1/chat/modelos").status_code == 200


def test_cookie_adulterado_vale_como_sem_sessao(cliente, auth_ligada):
    token, _ = criar_token("empresa", EMPRESA_EMAIL)
    cliente.cookies.set(NOME_COOKIE, token[:-2] + ("AA" if not token.endswith("AA") else "BB"))
    assert cliente.get("/api/v1/alunos").status_code == 401


def test_cookie_de_outro_segredo_nao_vale(cliente, auth_ligada):
    token, _ = criar_token("empresa", EMPRESA_EMAIL, segredo="x" * 40)
    cliente.cookies.set(NOME_COOKIE, token)
    assert cliente.get("/api/v1/alunos").status_code == 401


def test_aluno_usa_o_id_da_sessao_e_ignora_a_query(
    cliente, auth_ligada, semear_aluno, semear_material, vincular
):
    ana = semear_aluno(nome="Ana")
    bia = semear_aluno(nome="Bia")
    da_ana = vincular(ana, semear_material(visibilidade="publicado", titulo="Material da Ana"))
    da_bia = vincular(bia, semear_material(visibilidade="publicado", titulo="Material da Bia"))
    _entrar_como(cliente, "aluno", ana, nome="Ana")

    lista = cliente.get(f"/api/v1/aluno/materiais?aluno_id={bia}").json()
    assert [item["material_id"] for item in lista["itens"]] == [da_ana]
    sem_query = cliente.get("/api/v1/aluno/materiais").json()
    assert sem_query == lista

    assert cliente.get(f"/api/v1/aluno/materiais/{da_ana}?aluno_id={bia}").status_code == 200
    assert cliente.get(f"/api/v1/aluno/materiais/{da_bia}?aluno_id={bia}").status_code == 404
    assert cliente.get(f"/api/v1/aluno/materiais/{da_bia}").status_code == 404


def test_identificacao_publica_some_com_o_login(cliente, auth_ligada, semear_aluno):
    semear_aluno()
    assert cliente.get("/api/v1/aluno/identificacao").status_code == 404
    _entrar_como(cliente, "empresa", EMPRESA_EMAIL)
    assert cliente.get("/api/v1/aluno/identificacao").status_code == 404


@pytest.mark.parametrize("rota", ["/api/v1/health", "/api/v1/auth/config", "/docs", "/openapi.json", "/redoc"])
def test_rotas_publicas(cliente, auth_ligada, rota):
    assert cliente.get(rota).status_code == 200


def test_todas_as_rotas_tem_guarda_ou_sao_publicas(auth_ligada):
    """Uma rota nova sem guarda faz este teste falhar."""
    from fastapi.routing import APIRoute

    from app.auth import guardas
    from app.main import app

    publicas = {"/api/v1/health", "/api/v1/auth/config"}
    guardas_validas = {
        guardas.exigir_empresa, guardas.exigir_aluno, guardas.exigir_sessao,
        guardas.so_sem_login, guardas.auth_ligada,
    }

    def chamadas(dependant):
        for dep in dependant.dependencies:
            yield dep.call
            yield from chamadas(dep)

    sem_guarda = [
        rota.path for rota in app.routes
        if isinstance(rota, APIRoute) and rota.path not in publicas
        and not guardas_validas & set(chamadas(rota.dependant))
    ]
    assert sem_guarda == []
