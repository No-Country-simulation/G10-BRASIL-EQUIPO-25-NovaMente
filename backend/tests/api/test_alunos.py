"""Testes da API de alunos (área da empresa)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import func, select

from app.models.db import AlunoDB, MaterialDB, VinculoDB


# ── Helpers ───────────────────────────────────────────────────────────────────


def _vincular(db_session, aluno_id: str, material_id: str) -> None:
    db_session.add(
        VinculoDB(
            aluno_id=aluno_id,
            material_id=material_id,
            criado_em=datetime.now(timezone.utc).isoformat(),
        )
    )
    db_session.commit()


def _criar(cliente, nome: str = "Ana Silva", email: str = "ana@exemplo.com", **extra):
    return cliente.post(
        "/api/v1/alunos", json={"nome": nome, "email": email, **extra}
    )


def _emails(resp) -> list[str]:
    return [item["email"] for item in resp.json()["itens"]]


# ── POST /alunos ──────────────────────────────────────────────────────────────


def test_criar_aluno_retorna_201_e_normaliza_email(cliente):
    resp = _criar(cliente, nome="  Ana Silva  ", email="  Ana@Exemplo.COM  ")

    assert resp.status_code == 201
    corpo = resp.json()
    assert len(corpo["aluno_id"]) == 26
    assert corpo["nome"] == "Ana Silva"
    assert corpo["email"] == "ana@exemplo.com"
    assert corpo["status"] == "ativo"
    assert corpo["total_materiais"] == 0
    assert corpo["criado_em"]
    assert corpo["atualizado_em"]
    assert set(corpo) == {
        "aluno_id",
        "nome",
        "email",
        "status",
        "total_materiais",
        "criado_em",
        "atualizado_em",
    }

    listagem = cliente.get("/api/v1/alunos")
    assert [item["aluno_id"] for item in listagem.json()["itens"]] == [
        corpo["aluno_id"]
    ]


def test_email_duplicado_case_insensitive_retorna_409(cliente):
    cliente.post(
        "/api/v1/alunos", json={"nome": "Ana", "email": "Ana@Exemplo.com"}
    )
    resp = cliente.post(
        "/api/v1/alunos", json={"nome": "Bia", "email": "ana@exemplo.com"}
    )

    assert resp.status_code == 409
    assert resp.json()["erro"]["codigo"] == "EMAIL_JA_CADASTRADO"
    assert resp.json()["erro"]["campos"]["email"] == "E-mail já cadastrado."
    assert cliente.get("/api/v1/alunos").json()["total"] == 1


def test_email_duplicado_com_espacos_retorna_409(cliente):
    _criar(cliente, email="ana@exemplo.com")

    resp = _criar(cliente, nome="Bia", email="  ANA@EXEMPLO.COM ")

    assert resp.status_code == 409
    assert resp.json()["erro"]["codigo"] == "EMAIL_JA_CADASTRADO"


def test_email_duplicado_considera_linha_existente_em_caixa_alta(
    cliente, semear_aluno
):
    semear_aluno(nome="Ana", email="Ana@Exemplo.com")

    resp = _criar(cliente, nome="Bia", email="ana@exemplo.com")

    assert resp.status_code == 409
    assert resp.json()["erro"]["codigo"] == "EMAIL_JA_CADASTRADO"


@pytest.mark.parametrize(
    ("corpo", "campo"),
    [
        ({"nome": "ab", "email": "ana@exemplo.com"}, "nome"),
        ({"nome": "   ab   ", "email": "ana@exemplo.com"}, "nome"),
        ({"email": "ana@exemplo.com"}, "nome"),
        ({"nome": "Ana", "email": "invalido"}, "email"),
        ({"nome": "Ana"}, "email"),
        ({"nome": "Ana", "email": "ana@exemplo.com", "status": "invalido"}, "status"),
    ],
)
def test_criar_aluno_rejeita_corpo_invalido(cliente, corpo, campo):
    resp = cliente.post("/api/v1/alunos", json=corpo)

    assert resp.status_code == 422
    assert resp.json()["erro"]["codigo"] == "VALIDACAO"
    assert campo in resp.json()["erro"]["campos"]


# ── GET /alunos ───────────────────────────────────────────────────────────────


def test_listar_alunos_vazio(cliente):
    resp = cliente.get("/api/v1/alunos")

    assert resp.status_code == 200
    assert resp.json() == {
        "itens": [],
        "pagina": 1,
        "tamanho_pagina": 12,
        "total": 0,
        "total_paginas": 0,
    }


def test_listar_alunos_busca_q_em_nome_e_email_case_insensitive(
    cliente, semear_aluno
):
    so_nome = semear_aluno(nome="Ana Redes", email="ana.redes@exemplo.com")
    so_email = semear_aluno(nome="Bruno", email="redes@exemplo.com")
    semear_aluno(nome="Carla", email="carla@outro.com")

    resp = cliente.get("/api/v1/alunos", params={"q": "REDES"})

    assert resp.status_code == 200
    assert sorted(item["aluno_id"] for item in resp.json()["itens"]) == sorted(
        [so_nome, so_email]
    )
    assert resp.json()["total"] == 2


def test_listar_alunos_filtra_status(cliente, semear_aluno):
    ativo = semear_aluno(nome="Ana", status="ativo")
    semear_aluno(nome="Bia", status="inativo")

    resp = cliente.get("/api/v1/alunos", params={"status": "ativo"})

    assert resp.status_code == 200
    assert [item["aluno_id"] for item in resp.json()["itens"]] == [ativo]


@pytest.mark.parametrize(
    ("ordenar", "esperado"),
    [
        ("nome:asc", ["Ana", "Bia", "Caio"]),
        ("nome:desc", ["Caio", "Bia", "Ana"]),
        ("criado_em:desc", ["Ana", "Bia", "Caio"]),
    ],
)
def test_listar_alunos_ordena(cliente, semear_aluno, ordenar, esperado):
    semear_aluno(
        nome="Bia", email="bia@exemplo.com", criado_em="2026-01-02T00:00:00+00:00"
    )
    semear_aluno(
        nome="Ana", email="ana@exemplo.com", criado_em="2026-01-03T00:00:00+00:00"
    )
    semear_aluno(
        nome="Caio", email="caio@exemplo.com", criado_em="2026-01-01T00:00:00+00:00"
    )

    resp = cliente.get("/api/v1/alunos", params={"ordenar": ordenar})

    assert resp.status_code == 200
    assert [item["nome"] for item in resp.json()["itens"]] == esperado


def test_listar_alunos_pagina(cliente, semear_aluno):
    for indice in (1, 2, 3):
        semear_aluno(nome=f"Aluno {indice}", email=f"aluno{indice}@exemplo.com")

    primeira = cliente.get(
        "/api/v1/alunos", params={"pagina": 1, "tamanho_pagina": 2}
    ).json()
    segunda = cliente.get(
        "/api/v1/alunos", params={"pagina": 2, "tamanho_pagina": 2}
    ).json()

    assert primeira["total"] == 3
    assert primeira["total_paginas"] == 2
    assert [item["nome"] for item in primeira["itens"]] == ["Aluno 1", "Aluno 2"]
    assert segunda["pagina"] == 2
    assert [item["nome"] for item in segunda["itens"]] == ["Aluno 3"]


def test_listar_alunos_informa_total_de_materiais(
    cliente, db_session, semear_aluno, semear_material
):
    com_dois = semear_aluno(nome="Ana", email="ana@exemplo.com")
    com_um = semear_aluno(nome="Bia", email="bia@exemplo.com")
    _vincular(db_session, com_dois, semear_material())
    _vincular(db_session, com_dois, semear_material())
    _vincular(db_session, com_um, semear_material())

    itens = {
        item["aluno_id"]: item["total_materiais"]
        for item in cliente.get("/api/v1/alunos").json()["itens"]
    }

    assert itens == {com_dois: 2, com_um: 1}


@pytest.mark.parametrize(
    "query",
    [
        "pagina=0",
        "tamanho_pagina=0",
        "tamanho_pagina=51",
        "q=",
        "status=invalido",
        "ordenar=invalido",
    ],
)
def test_listar_alunos_parametros_invalidos(cliente, query):
    resp = cliente.get(f"/api/v1/alunos?{query}")

    assert resp.status_code == 422
    assert resp.json()["erro"]["codigo"] == "VALIDACAO"


# ── GET /alunos/{aluno_id} ────────────────────────────────────────────────────


def test_obter_aluno(cliente, semear_aluno):
    aluno_id = semear_aluno(nome="Ana Silva", email="ana@exemplo.com")

    resp = cliente.get(f"/api/v1/alunos/{aluno_id}")

    assert resp.status_code == 200
    assert resp.json()["aluno_id"] == aluno_id
    assert resp.json()["nome"] == "Ana Silva"
    assert resp.json()["total_materiais"] == 0


def test_obter_aluno_inexistente(cliente):
    resp = cliente.get("/api/v1/alunos/NAO_EXISTE")

    assert resp.status_code == 404
    assert resp.json()["erro"]["codigo"] == "ALUNO_NAO_ENCONTRADO"


# ── PATCH /alunos/{aluno_id} ──────────────────────────────────────────────────


def test_patch_aluno_parcial(cliente, semear_aluno):
    aluno_id = semear_aluno(
        nome="Ana Silva",
        email="ana@exemplo.com",
        criado_em="2020-01-01T00:00:00+00:00",
        atualizado_em="2020-01-01T00:00:00+00:00",
    )

    resp = cliente.patch(
        f"/api/v1/alunos/{aluno_id}", json={"nome": "  Ana Souza  "}
    )

    assert resp.status_code == 200
    corpo = resp.json()
    assert corpo["nome"] == "Ana Souza"
    assert corpo["email"] == "ana@exemplo.com"
    assert corpo["status"] == "ativo"
    assert corpo["atualizado_em"] != "2020-01-01T00:00:00+00:00"
    assert cliente.get(f"/api/v1/alunos/{aluno_id}").json()["nome"] == "Ana Souza"


def test_patch_aluno_normaliza_email_do_proprio_aluno(cliente, semear_aluno):
    aluno_id = semear_aluno(email="ana@exemplo.com")

    resp = cliente.patch(
        f"/api/v1/alunos/{aluno_id}", json={"email": "  ANA@Exemplo.COM "}
    )

    assert resp.status_code == 200
    assert resp.json()["email"] == "ana@exemplo.com"


def test_patch_aluno_atualiza_status(cliente, semear_aluno):
    aluno_id = semear_aluno(status="ativo")

    resp = cliente.patch(f"/api/v1/alunos/{aluno_id}", json={"status": "inativo"})

    assert resp.status_code == 200
    assert resp.json()["status"] == "inativo"


def test_patch_email_de_outro_aluno_retorna_409(cliente, semear_aluno):
    semear_aluno(email="ana@exemplo.com")
    aluno_id = semear_aluno(email="bia@exemplo.com")

    resp = cliente.patch(
        f"/api/v1/alunos/{aluno_id}", json={"email": "ANA@exemplo.com"}
    )

    assert resp.status_code == 409
    assert resp.json()["erro"]["codigo"] == "EMAIL_JA_CADASTRADO"
    assert resp.json()["erro"]["campos"]["email"] == "E-mail já cadastrado."


def test_patch_aluno_e_404(cliente):
    resp = cliente.patch(
        "/api/v1/alunos/NAO_EXISTE", json={"nome": "Ana Silva"}
    )

    assert resp.status_code == 404
    assert resp.json()["erro"]["codigo"] == "ALUNO_NAO_ENCONTRADO"


@pytest.mark.parametrize(
    "corpo",
    [
        {},
        {"nome": None},
        {"nome": "ab"},
        {"email": "invalido"},
        {"status": "invalido"},
        {"campo_desconhecido": "x"},
    ],
)
def test_patch_aluno_rejeita_corpo_invalido(cliente, semear_aluno, corpo):
    aluno_id = semear_aluno()

    resp = cliente.patch(f"/api/v1/alunos/{aluno_id}", json=corpo)

    assert resp.status_code == 422
    assert resp.json()["erro"]["codigo"] == "VALIDACAO"


# ── DELETE /alunos/{aluno_id} ─────────────────────────────────────────────────


def test_delete_aluno_204_e_cascata_de_vinculos(
    cliente, db_session, semear_aluno, semear_material
):
    aluno_id = semear_aluno()
    material_id = semear_material()
    _vincular(db_session, aluno_id, material_id)

    resp = cliente.delete(f"/api/v1/alunos/{aluno_id}")

    assert resp.status_code == 204
    assert resp.content == b""
    assert cliente.get(f"/api/v1/alunos/{aluno_id}").status_code == 404
    assert (
        db_session.scalar(
            select(func.count())
            .select_from(VinculoDB)
            .where(VinculoDB.aluno_id == aluno_id)
        )
        == 0
    )
    # Materiais não são tocados ao excluir o aluno.
    assert db_session.get(MaterialDB, material_id) is not None
    assert db_session.scalar(select(func.count()).select_from(AlunoDB)) == 0


def test_delete_aluno_inexistente(cliente):
    resp = cliente.delete("/api/v1/alunos/NAO_EXISTE")

    assert resp.status_code == 404
    assert resp.json()["erro"]["codigo"] == "ALUNO_NAO_ENCONTRADO"
