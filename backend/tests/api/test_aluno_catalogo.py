"""Testes das rotas somente leitura da área do aluno."""

from __future__ import annotations

import pytest
from sqlalchemy import text


# ── Helpers ───────────────────────────────────────────────────────────────────


def _ids(resp) -> list[str]:
    return [item["material_id"] for item in resp.json()["itens"]]


# ── GET /aluno/identificacao ──────────────────────────────────────────────────


def test_identificacao_lista_somente_ativos_por_nome_sem_email(
    cliente, semear_aluno
):
    zulu = semear_aluno(nome="Zulu")
    ana = semear_aluno(nome="Ana")
    semear_aluno(nome="Inativo", status="inativo")

    resp = cliente.get("/api/v1/aluno/identificacao")

    assert resp.status_code == 200
    assert resp.json() == {
        "itens": [
            {"aluno_id": ana, "nome": "Ana"},
            {"aluno_id": zulu, "nome": "Zulu"},
        ]
    }


def test_identificacao_vazia(cliente):
    resp = cliente.get("/api/v1/aluno/identificacao")

    assert resp.status_code == 200
    assert resp.json() == {"itens": []}


# ── GET /aluno/materiais ──────────────────────────────────────────────────────


def test_catalogo_so_publicado_e_vinculado(
    cliente, semear_aluno, semear_material, vincular
):
    aluno = semear_aluno()
    publicado = semear_material(visibilidade="publicado")
    rascunho = semear_material(visibilidade="rascunho")
    outro = semear_material(visibilidade="publicado")
    vincular(aluno, publicado)

    resp = cliente.get(f"/api/v1/aluno/materiais?aluno_id={aluno}")

    assert resp.status_code == 200
    assert [i["material_id"] for i in resp.json()["itens"]] == [publicado]
    assert (
        cliente.get(
            f"/api/v1/aluno/materiais/{rascunho}?aluno_id={aluno}"
        ).status_code
        == 404
    )
    assert (
        cliente.get(
            f"/api/v1/aluno/materiais/{outro}?aluno_id={aluno}"
        ).status_code
        == 404
    )


def test_catalogo_aluno_inexistente_404(cliente):
    resp = cliente.get("/api/v1/aluno/materiais?aluno_id=NAO_EXISTE")

    assert resp.status_code == 404
    assert resp.json()["erro"]["codigo"] == "ALUNO_NAO_ENCONTRADO"


def test_catalogo_aluno_inativo_403(cliente, semear_aluno):
    aluno = semear_aluno(status="inativo")

    resp = cliente.get(f"/api/v1/aluno/materiais?aluno_id={aluno}")

    assert resp.status_code == 403
    assert resp.json()["erro"]["codigo"] == "ALUNO_INATIVO"


def test_catalogo_devolve_campos_do_item_e_conceitos_limitados(
    cliente, semear_aluno, semear_material, vincular
):
    aluno = semear_aluno()
    material = semear_material(
        titulo="Material de Redes",
        documento_titulo="Manual de Redes",
        formato="Quiz",
        perfil="Desenvolvedor",
        nivel="Tecnico",
        tempo_estimado_minutos=7,
        criado_em="2026-01-02T10:00:00+00:00",
        conceitos_chave_json='["A","B","C","D","E","F","G"]',
        visibilidade="publicado",
    )
    vincular(aluno, material)

    resp = cliente.get(f"/api/v1/aluno/materiais?aluno_id={aluno}")

    assert resp.status_code == 200
    assert resp.json()["itens"] == [
        {
            "material_id": material,
            "titulo": "Material de Redes",
            "documento_titulo": "Manual de Redes",
            "formato": "Quiz",
            "perfil": "Desenvolvedor",
            "nivel": "Tecnico",
            "tempo_estimado_estudo_minutos": 7,
            "criado_em": "2026-01-02T10:00:00+00:00",
            "conceitos_chave": ["A", "B", "C", "D", "E", "F"],
        }
    ]


def test_catalogo_filtra_por_q_formato_e_perfil(
    cliente, semear_aluno, semear_material, vincular
):
    aluno = semear_aluno()

    alvo = semear_material(
        titulo="Redes Neurais",
        documento_titulo="Guia",
        formato="Quiz",
        perfil="Desenvolvedor",
        visibilidade="publicado",
    )
    so_documento = semear_material(
        titulo="Introdução",
        documento_titulo="Manual de Redes",
        formato="Flashcards",
        perfil="Iniciante",
        visibilidade="publicado",
    )
    semear_material(
        titulo="Cloud",
        documento_titulo="Guia de Cloud",
        formato="Quiz",
        perfil="Desenvolvedor",
        visibilidade="publicado",
    )
    for material in (alvo, so_documento):
        vincular(aluno, material)

    por_q = cliente.get(
        "/api/v1/aluno/materiais", params={"aluno_id": aluno, "q": "redes"}
    )
    assert por_q.status_code == 200
    assert sorted(_ids(por_q)) == sorted([alvo, so_documento])
    assert por_q.json()["total"] == 2

    por_formato = cliente.get(
        "/api/v1/aluno/materiais",
        params={"aluno_id": aluno, "formato": "Quiz"},
    )
    assert por_formato.status_code == 200
    assert _ids(por_formato) == [alvo]

    por_perfil = cliente.get(
        "/api/v1/aluno/materiais",
        params={"aluno_id": aluno, "perfil": "Iniciante"},
    )
    assert por_perfil.status_code == 200
    assert _ids(por_perfil) == [so_documento]


@pytest.mark.parametrize(
    ("ordenar", "esperado"),
    [
        ("criado_em:desc", ["Alfa", "Gama", "Beta"]),
        ("titulo:asc", ["Alfa", "Beta", "Gama"]),
    ],
)
def test_catalogo_ordena(
    cliente, semear_aluno, semear_material, vincular, ordenar, esperado
):
    aluno = semear_aluno()
    materiais = [
        semear_material(
            titulo="Beta",
            criado_em="2026-01-01T00:00:00+00:00",
            visibilidade="publicado",
        ),
        semear_material(
            titulo="Alfa",
            criado_em="2026-01-03T00:00:00+00:00",
            visibilidade="publicado",
        ),
        semear_material(
            titulo="Gama",
            criado_em="2026-01-02T00:00:00+00:00",
            visibilidade="publicado",
        ),
    ]
    for material in materiais:
        vincular(aluno, material)

    resp = cliente.get(
        "/api/v1/aluno/materiais",
        params={"aluno_id": aluno, "ordenar": ordenar},
    )

    assert resp.status_code == 200
    assert [item["titulo"] for item in resp.json()["itens"]] == esperado


def test_catalogo_pagina(cliente, semear_aluno, semear_material, vincular):
    aluno = semear_aluno()
    materiais = [
        semear_material(
            titulo=f"Material {dia}",
            criado_em=f"2026-01-0{dia}T00:00:00+00:00",
            visibilidade="publicado",
        )
        for dia in (1, 2, 3)
    ]
    for material in materiais:
        vincular(aluno, material)

    primeira = cliente.get(
        "/api/v1/aluno/materiais",
        params={"aluno_id": aluno, "pagina": 1, "tamanho_pagina": 2},
    ).json()
    segunda = cliente.get(
        "/api/v1/aluno/materiais",
        params={"aluno_id": aluno, "pagina": 2, "tamanho_pagina": 2},
    ).json()

    assert primeira["total"] == 3
    assert primeira["total_paginas"] == 2
    assert [item["titulo"] for item in primeira["itens"]] == [
        "Material 3",
        "Material 2",
    ]
    assert segunda["pagina"] == 2
    assert [item["titulo"] for item in segunda["itens"]] == ["Material 1"]


def test_catalogo_vazio(
    cliente, semear_aluno, semear_material, vincular
):
    aluno = semear_aluno()
    # Rascunho e material de outro aluno nunca aparecem.
    vincular(aluno, semear_material(visibilidade="rascunho"))
    semear_material(visibilidade="publicado")

    resp = cliente.get(f"/api/v1/aluno/materiais?aluno_id={aluno}")

    assert resp.status_code == 200
    assert resp.json() == {
        "itens": [],
        "pagina": 1,
        "tamanho_pagina": 12,
        "total": 0,
        "total_paginas": 0,
    }


def test_catalogo_nao_abre_pacote_json(
    cliente, db_session, semear_aluno, semear_material, vincular
):
    aluno = semear_aluno()
    material = semear_material(visibilidade="publicado")
    vincular(aluno, material)
    db_session.execute(text("UPDATE materiais SET pacote_json='{'"))
    db_session.commit()

    resp = cliente.get(f"/api/v1/aluno/materiais?aluno_id={aluno}")

    assert resp.status_code == 200
    assert _ids(resp) == [material]


@pytest.mark.parametrize(
    "query",
    [
        "",
        "aluno_id=",
        "aluno_id=QUALQUER&pagina=0",
        "aluno_id=QUALQUER&tamanho_pagina=51",
        "aluno_id=QUALQUER&ordenar=invalido",
        "aluno_id=QUALQUER&formato=Inexistente",
        "aluno_id=QUALQUER&perfil=Inexistente",
    ],
)
def test_catalogo_parametros_invalidos(cliente, query):
    resp = cliente.get(f"/api/v1/aluno/materiais?{query}")

    assert resp.status_code == 422
    assert resp.json()["erro"]["codigo"] == "VALIDACAO"


# ── GET /aluno/materiais/{material_id} ────────────────────────────────────────


def test_obter_material_do_aluno(
    cliente, semear_aluno, semear_material, vincular
):
    aluno = semear_aluno()
    material = semear_material(titulo="Material de Redes", visibilidade="publicado")
    vincular(aluno, material)

    resp = cliente.get(
        f"/api/v1/aluno/materiais/{material}?aluno_id={aluno}"
    )

    assert resp.status_code == 200
    corpo = resp.json()
    assert corpo["material"]["material_id"] == material
    assert corpo["material"]["titulo"] == "Material de Redes"
    assert corpo["pacote"]["adaptacao_id"] == material
    assert corpo["pacote"]["conteudo_adaptado"]["tipo"] == "flashcards"


def test_obter_material_inexistente_404(cliente, semear_aluno):
    aluno = semear_aluno()

    resp = cliente.get(
        f"/api/v1/aluno/materiais/NAO_EXISTE?aluno_id={aluno}"
    )

    assert resp.status_code == 404
    assert resp.json()["erro"]["codigo"] == "MATERIAL_NAO_DISPONIVEL"


def test_obter_material_rascunho_404(
    cliente, semear_aluno, semear_material, vincular
):
    aluno = semear_aluno()
    material = semear_material(visibilidade="rascunho")
    vincular(aluno, material)

    resp = cliente.get(
        f"/api/v1/aluno/materiais/{material}?aluno_id={aluno}"
    )

    assert resp.status_code == 404
    assert resp.json()["erro"]["codigo"] == "MATERIAL_NAO_DISPONIVEL"


def test_obter_material_nao_vinculado_404(
    cliente, semear_aluno, semear_material
):
    aluno = semear_aluno()
    material = semear_material(visibilidade="publicado")

    resp = cliente.get(
        f"/api/v1/aluno/materiais/{material}?aluno_id={aluno}"
    )

    assert resp.status_code == 404
    assert resp.json()["erro"]["codigo"] == "MATERIAL_NAO_DISPONIVEL"


def test_obter_material_aluno_inexistente_404(cliente, semear_material):
    material = semear_material(visibilidade="publicado")

    resp = cliente.get(
        f"/api/v1/aluno/materiais/{material}?aluno_id=NAO_EXISTE"
    )

    assert resp.status_code == 404
    assert resp.json()["erro"]["codigo"] == "ALUNO_NAO_ENCONTRADO"


def test_obter_material_aluno_inativo_403(
    cliente, semear_aluno, semear_material, vincular
):
    aluno = semear_aluno(status="inativo")
    material = semear_material(visibilidade="publicado")
    vincular(aluno, material)

    resp = cliente.get(
        f"/api/v1/aluno/materiais/{material}?aluno_id={aluno}"
    )

    assert resp.status_code == 403
    assert resp.json()["erro"]["codigo"] == "ALUNO_INATIVO"


def test_obter_material_sem_aluno_id_422(cliente, semear_material):
    material = semear_material(visibilidade="publicado")

    resp = cliente.get(f"/api/v1/aluno/materiais/{material}")

    assert resp.status_code == 422
    assert resp.json()["erro"]["codigo"] == "VALIDACAO"


def test_obter_material_pacote_corrompido_500(
    cliente, db_session, semear_aluno, semear_material, vincular
):
    aluno = semear_aluno()
    material = semear_material(visibilidade="publicado")
    vincular(aluno, material)
    db_session.execute(text("UPDATE materiais SET pacote_json='{'"))
    db_session.commit()

    resp = cliente.get(
        f"/api/v1/aluno/materiais/{material}?aluno_id={aluno}"
    )

    assert resp.status_code == 500
    erro = resp.json()["erro"]
    assert erro["codigo"] == "INTERNO"
    assert "request_id" in erro
