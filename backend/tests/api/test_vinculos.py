"""Testes da API de vínculos entre alunos e materiais (área da empresa)."""

from __future__ import annotations

import pytest
from sqlalchemy import func, select, text

from app.models.db import VinculoDB


# ── Helpers ───────────────────────────────────────────────────────────────────


def _ids(resp) -> list[str]:
    return [item["material_id"] for item in resp.json()["itens"]]


def _total_vinculos(db_session) -> int:
    return db_session.scalar(select(func.count()).select_from(VinculoDB))


# ── GET /alunos/{aluno_id}/materiais ─────────────────────────────────────────


def test_get_vinculos_vazio(cliente, semear_aluno):
    aluno_id = semear_aluno()

    resp = cliente.get(f"/api/v1/alunos/{aluno_id}/materiais")

    assert resp.status_code == 200
    assert resp.json() == {"aluno_id": aluno_id, "itens": []}


def test_get_vinculos_aluno_inexistente_404(cliente):
    resp = cliente.get("/api/v1/alunos/NAO_EXISTE/materiais")

    assert resp.status_code == 404
    assert resp.json()["erro"]["codigo"] == "ALUNO_NAO_ENCONTRADO"


def test_get_vinculos_ordenado_por_vinculado_em_desc(
    cliente, semear_aluno, semear_material, vincular
):
    aluno_id = semear_aluno()
    antigo = semear_material(titulo="Antigo")
    novo = semear_material(titulo="Novo")
    vincular(aluno_id, antigo, criado_em="2026-01-01T00:00:00+00:00")
    vincular(aluno_id, novo, criado_em="2026-02-01T00:00:00+00:00")

    resp = cliente.get(f"/api/v1/alunos/{aluno_id}/materiais")

    assert resp.status_code == 200
    assert _ids(resp) == [novo, antigo]
    assert resp.json()["itens"][0] == {
        "material_id": novo,
        "titulo": "Novo",
        "formato": "Flashcards",
        "perfil": "Iniciante",
        "visibilidade": "rascunho",
        "vinculado_em": "2026-02-01T00:00:00+00:00",
    }


def test_get_vinculos_nao_abre_pacote_json(
    cliente, db_session, semear_aluno, semear_material, vincular
):
    aluno_id = semear_aluno()
    material_id = semear_material()
    vincular(aluno_id, material_id)
    db_session.execute(text("UPDATE materiais SET pacote_json='{'"))
    db_session.commit()

    resp = cliente.get(f"/api/v1/alunos/{aluno_id}/materiais")

    assert resp.status_code == 200
    assert _ids(resp) == [material_id]


# ── PUT /alunos/{aluno_id}/materiais ─────────────────────────────────────────


def test_put_vinculos_e_atomico(cliente, semear_aluno, semear_material):
    aluno = semear_aluno()
    m1, m2 = semear_material(), semear_material()

    resp = cliente.put(
        f"/api/v1/alunos/{aluno}/materiais",
        json={"material_ids": [m1, "INEXISTENTE"]},
    )

    assert resp.status_code == 422
    assert resp.json()["erro"]["campos"]["material_ids"]
    assert cliente.get(f"/api/v1/alunos/{aluno}/materiais").json()["itens"] == []


def test_put_vinculos_invalido_preserva_vinculos_existentes(
    cliente, semear_aluno, semear_material, vincular
):
    aluno_id = semear_aluno()
    existente = semear_material()
    vincular(aluno_id, existente)

    resp = cliente.put(
        f"/api/v1/alunos/{aluno_id}/materiais",
        json={"material_ids": [semear_material(), "INEXISTENTE"]},
    )

    assert resp.status_code == 422
    assert _ids(cliente.get(f"/api/v1/alunos/{aluno_id}/materiais")) == [existente]


def test_put_vinculos_substitui_e_deduplica(
    cliente, db_session, semear_aluno, semear_material, vincular
):
    aluno_id = semear_aluno()
    antigo = semear_material()
    novo = semear_material()
    vincular(aluno_id, antigo)

    resp = cliente.put(
        f"/api/v1/alunos/{aluno_id}/materiais",
        json={"material_ids": [novo, novo]},
    )

    assert resp.status_code == 200
    assert _ids(resp) == [novo]
    assert _ids(cliente.get(f"/api/v1/alunos/{aluno_id}/materiais")) == [novo]
    assert _total_vinculos(db_session) == 1


def test_put_vinculos_lista_vazia_remove_todos(
    cliente, semear_aluno, semear_material, vincular
):
    aluno_id = semear_aluno()
    vincular(aluno_id, semear_material())
    vincular(aluno_id, semear_material())

    resp = cliente.put(
        f"/api/v1/alunos/{aluno_id}/materiais", json={"material_ids": []}
    )

    assert resp.status_code == 200
    assert resp.json() == {"aluno_id": aluno_id, "itens": []}
    assert cliente.get(f"/api/v1/alunos/{aluno_id}/materiais").json()["itens"] == []


def test_put_vinculos_aluno_inexistente_404(cliente, semear_material):
    resp = cliente.put(
        "/api/v1/alunos/NAO_EXISTE/materiais",
        json={"material_ids": [semear_material()]},
    )

    assert resp.status_code == 404
    assert resp.json()["erro"]["codigo"] == "ALUNO_NAO_ENCONTRADO"


@pytest.mark.parametrize(
    "corpo",
    [
        {},
        {"material_ids": None},
        {"material_ids": [str(indice) for indice in range(501)]},
    ],
)
def test_put_vinculos_rejeita_corpo_invalido(cliente, semear_aluno, corpo):
    aluno_id = semear_aluno()

    resp = cliente.put(f"/api/v1/alunos/{aluno_id}/materiais", json=corpo)

    assert resp.status_code == 422
    assert resp.json()["erro"]["codigo"] == "VALIDACAO"


# ── POST /alunos/{aluno_id}/materiais/{material_id} ──────────────────────────


def test_post_vinculo_201_na_criacao_e_200_se_ja_existe(
    cliente, semear_aluno, semear_material
):
    aluno_id = semear_aluno()
    material_id = semear_material(titulo="Material vinculado")

    primeira = cliente.post(f"/api/v1/alunos/{aluno_id}/materiais/{material_id}")

    assert primeira.status_code == 201
    corpo = primeira.json()
    assert corpo == {
        "material_id": material_id,
        "titulo": "Material vinculado",
        "formato": "Flashcards",
        "perfil": "Iniciante",
        "visibilidade": "rascunho",
        "vinculado_em": corpo["vinculado_em"],
    }

    segunda = cliente.post(f"/api/v1/alunos/{aluno_id}/materiais/{material_id}")

    assert segunda.status_code == 200
    assert segunda.json() == corpo
    assert _ids(cliente.get(f"/api/v1/alunos/{aluno_id}/materiais")) == [
        material_id
    ]


def test_post_vinculo_aluno_inexistente_404(cliente, semear_material):
    material_id = semear_material()

    resp = cliente.post(f"/api/v1/alunos/NAO_EXISTE/materiais/{material_id}")

    assert resp.status_code == 404
    assert resp.json()["erro"]["codigo"] == "ALUNO_NAO_ENCONTRADO"


def test_post_vinculo_material_inexistente_404(cliente, semear_aluno):
    aluno_id = semear_aluno()

    resp = cliente.post(f"/api/v1/alunos/{aluno_id}/materiais/NAO_EXISTE")

    assert resp.status_code == 404
    assert resp.json()["erro"]["codigo"] == "MATERIAL_NAO_ENCONTRADO"


# ── DELETE /alunos/{aluno_id}/materiais/{material_id} ────────────────────────


def test_delete_vinculo_204_idempotente(
    cliente, semear_aluno, semear_material, vincular
):
    aluno_id = semear_aluno()
    material_id = semear_material()
    vincular(aluno_id, material_id)

    primeira = cliente.delete(
        f"/api/v1/alunos/{aluno_id}/materiais/{material_id}"
    )
    segunda = cliente.delete(
        f"/api/v1/alunos/{aluno_id}/materiais/{material_id}"
    )

    assert primeira.status_code == 204
    assert primeira.content == b""
    assert segunda.status_code == 204
    assert segunda.content == b""
    assert cliente.get(f"/api/v1/alunos/{aluno_id}/materiais").json()["itens"] == []


def test_delete_vinculo_aluno_inexistente_404(cliente, semear_material):
    material_id = semear_material()

    resp = cliente.delete(f"/api/v1/alunos/NAO_EXISTE/materiais/{material_id}")

    assert resp.status_code == 404
    assert resp.json()["erro"]["codigo"] == "ALUNO_NAO_ENCONTRADO"


def test_delete_vinculo_material_inexistente_404(cliente, semear_aluno):
    aluno_id = semear_aluno()

    resp = cliente.delete(f"/api/v1/alunos/{aluno_id}/materiais/NAO_EXISTE")

    assert resp.status_code == 404
    assert resp.json()["erro"]["codigo"] == "MATERIAL_NAO_ENCONTRADO"


# ── Cascata ──────────────────────────────────────────────────────────────────


def test_excluir_material_remove_vinculo_da_listagem(
    cliente, semear_aluno, semear_material, vincular, monkeypatch
):
    aluno_id = semear_aluno()
    material_id = semear_material()
    vincular(aluno_id, material_id)
    monkeypatch.setattr(
        "app.api.v1.routers.materiais.remover_objeto", lambda _: True
    )

    assert cliente.delete(f"/api/v1/materiais/{material_id}").status_code == 200

    assert cliente.get(f"/api/v1/alunos/{aluno_id}/materiais").json()["itens"] == []
