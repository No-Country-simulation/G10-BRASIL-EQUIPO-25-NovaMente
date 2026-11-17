"""Testes da API de materiais (empresa) e da remoção de objetos no OCI."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import func, select, text

from app.models.db import AlunoDB, VinculoDB
from app.services import oci


# ── Helpers ───────────────────────────────────────────────────────────────────


def _semear_aluno(db_session, aluno_id: str = "ALUNO1") -> str:
    agora = datetime.now(timezone.utc).isoformat()
    db_session.add(
        AlunoDB(
            aluno_id=aluno_id,
            nome="Ana",
            email=f"{aluno_id.lower()}@exemplo.com",
            status="ativo",
            criado_em=agora,
            atualizado_em=agora,
        )
    )
    db_session.commit()
    return aluno_id


def _vincular(db_session, aluno_id: str, material_id: str) -> None:
    db_session.add(
        VinculoDB(
            aluno_id=aluno_id,
            material_id=material_id,
            criado_em=datetime.now(timezone.utc).isoformat(),
        )
    )
    db_session.commit()


def _ids(resp) -> list[str]:
    return [item["material_id"] for item in resp.json()["itens"]]


# ── GET /materiais ────────────────────────────────────────────────────────────


def test_listar_materiais_vazio(cliente):
    resp = cliente.get("/api/v1/materiais")

    assert resp.status_code == 200
    assert resp.json() == {
        "itens": [],
        "pagina": 1,
        "tamanho_pagina": 12,
        "total": 0,
        "total_paginas": 0,
    }


def test_listar_materiais_nao_quebra_com_pacote_corrompido(
    cliente, db_session, semear_material
):
    semear_material(visibilidade="publicado")
    db_session.execute(text("UPDATE materiais SET pacote_json='{'"))
    db_session.commit()

    resp = cliente.get("/api/v1/materiais")

    assert resp.status_code == 200
    assert resp.json()["itens"][0]["visibilidade"] == "publicado"


def test_listar_materiais_devolve_colunas_desnormalizadas(cliente, semear_material):
    mid = semear_material(
        titulo="Material de Redes",
        documento_titulo="Manual de Redes",
        perfil="Desenvolvedor",
        formato="Quiz",
        nivel="Tecnico",
        nicho="Fintech",
        tempo_estimado_minutos=7,
        ancoragem_score=0.77,
        status_upload="falha",
        visibilidade="publicado",
        criado_em="2026-01-02T10:00:00+00:00",
        atualizado_em="2026-01-03T11:00:00+00:00",
    )

    item = cliente.get("/api/v1/materiais").json()["itens"][0]

    assert item == {
        "material_id": mid,
        "adaptacao_id": mid,
        "titulo": "Material de Redes",
        "documento_titulo": "Manual de Redes",
        "perfil": "Desenvolvedor",
        "formato": "Quiz",
        "nivel": "Tecnico",
        "nicho": "Fintech",
        "visibilidade": "publicado",
        "tempo_estimado_estudo_minutos": 7,
        "ancoragem_fonte_score": 0.77,
        "status_upload": "falha",
        "criado_em": "2026-01-02T10:00:00+00:00",
        "atualizado_em": "2026-01-03T11:00:00+00:00",
    }


def test_listar_materiais_filtra_por_q_em_titulo_e_documento(
    cliente, semear_material
):
    so_titulo = semear_material(titulo="Redes Neurais", documento_titulo="Guia")
    so_documento = semear_material(
        titulo="Introdução", documento_titulo="Manual de Redes"
    )
    semear_material(titulo="Cloud", documento_titulo="Guia de Cloud")

    resp = cliente.get("/api/v1/materiais", params={"q": "redes"})

    assert resp.status_code == 200
    assert sorted(_ids(resp)) == sorted([so_titulo, so_documento])
    assert resp.json()["total"] == 2


def test_listar_materiais_filtra_formato_perfil_e_visibilidade(
    cliente, semear_material
):
    alvo = semear_material(
        formato="Quiz",
        perfil="Desenvolvedor",
        visibilidade="publicado",
    )
    semear_material(formato="Quiz", perfil="Iniciante", visibilidade="publicado")
    semear_material(formato="Flashcards", perfil="Desenvolvedor", visibilidade="publicado")
    semear_material(formato="Quiz", perfil="Desenvolvedor", visibilidade="rascunho")

    resp = cliente.get(
        "/api/v1/materiais",
        params={
            "formato": "Quiz",
            "perfil": "Desenvolvedor",
            "visibilidade": "publicado",
        },
    )

    assert resp.status_code == 200
    assert _ids(resp) == [alvo]


@pytest.mark.parametrize(
    ("ordenar", "esperado"),
    [
        ("criado_em:desc", ["Alfa", "Gama", "Beta"]),
        ("criado_em:asc", ["Beta", "Gama", "Alfa"]),
        ("ancoragem:desc", ["Beta", "Gama", "Alfa"]),
        ("titulo:asc", ["Alfa", "Beta", "Gama"]),
    ],
)
def test_listar_materiais_ordena(cliente, semear_material, ordenar, esperado):
    semear_material(
        titulo="Beta",
        criado_em="2026-01-01T00:00:00+00:00",
        ancoragem_score=0.9,
    )
    semear_material(
        titulo="Alfa",
        criado_em="2026-01-03T00:00:00+00:00",
        ancoragem_score=0.5,
    )
    semear_material(
        titulo="Gama",
        criado_em="2026-01-02T00:00:00+00:00",
        ancoragem_score=0.7,
    )

    resp = cliente.get("/api/v1/materiais", params={"ordenar": ordenar})

    assert resp.status_code == 200
    assert [item["titulo"] for item in resp.json()["itens"]] == esperado


def test_listar_materiais_pagina(cliente, semear_material):
    for dia in (1, 2, 3):
        semear_material(
            titulo=f"Material {dia}",
            criado_em=f"2026-01-0{dia}T00:00:00+00:00",
        )

    primeira = cliente.get(
        "/api/v1/materiais", params={"pagina": 1, "tamanho_pagina": 2}
    ).json()
    segunda = cliente.get(
        "/api/v1/materiais", params={"pagina": 2, "tamanho_pagina": 2}
    ).json()

    assert primeira["total"] == 3
    assert primeira["total_paginas"] == 2
    assert [item["titulo"] for item in primeira["itens"]] == [
        "Material 3",
        "Material 2",
    ]
    assert segunda["pagina"] == 2
    assert [item["titulo"] for item in segunda["itens"]] == ["Material 1"]


@pytest.mark.parametrize(
    "query",
    [
        "pagina=0",
        "tamanho_pagina=0",
        "tamanho_pagina=51",
        "q=",
        "ordenar=invalido",
        "formato=Inexistente",
        "perfil=Inexistente",
        "visibilidade=invalido",
    ],
)
def test_listar_materiais_parametros_invalidos(cliente, query):
    resp = cliente.get(f"/api/v1/materiais?{query}")

    assert resp.status_code == 422
    assert resp.json()["erro"]["codigo"] == "VALIDACAO"


# ── GET /materiais/{id} ───────────────────────────────────────────────────────


def test_obter_material_detalhe(cliente, semear_material):
    mid = semear_material(titulo="Material de Redes")

    resp = cliente.get(f"/api/v1/materiais/{mid}")

    assert resp.status_code == 200
    corpo = resp.json()
    assert corpo["material"]["material_id"] == mid
    assert corpo["material"]["titulo"] == "Material de Redes"
    assert corpo["pacote"]["adaptacao_id"] == mid
    assert corpo["pacote"]["conteudo_adaptado"]["tipo"] == "flashcards"


def test_obter_material_inexistente(cliente):
    resp = cliente.get("/api/v1/materiais/NAO_EXISTE")

    assert resp.status_code == 404
    assert resp.json()["erro"]["codigo"] == "MATERIAL_NAO_ENCONTRADO"


def test_obter_material_com_pacote_corrompido_retorna_500(
    cliente, db_session, semear_material
):
    mid = semear_material()
    db_session.execute(text("UPDATE materiais SET pacote_json='{'"))
    db_session.commit()

    resp = cliente.get(f"/api/v1/materiais/{mid}")

    assert resp.status_code == 500
    erro = resp.json()["erro"]
    assert erro["codigo"] == "INTERNO"
    assert "request_id" in erro


# ── PATCH /materiais/{id} ─────────────────────────────────────────────────────


def test_patch_atualiza_titulo_e_visibilidade(cliente, semear_material):
    mid = semear_material(
        titulo="Título original",
        criado_em="2020-01-01T00:00:00+00:00",
        atualizado_em="2020-01-01T00:00:00+00:00",
    )

    resp = cliente.patch(
        f"/api/v1/materiais/{mid}",
        json={"titulo": "  Título editado  ", "visibilidade": "publicado"},
    )

    assert resp.status_code == 200
    corpo = resp.json()
    assert corpo["titulo"] == "Título editado"
    assert corpo["visibilidade"] == "publicado"
    assert corpo["atualizado_em"] != "2020-01-01T00:00:00+00:00"

    detalhe = cliente.get(f"/api/v1/materiais/{mid}").json()
    assert detalhe["material"]["titulo"] == "Título editado"
    assert detalhe["material"]["visibilidade"] == "publicado"
    # Editar o catálogo não altera o pacote imutável.
    assert detalhe["pacote"]["conteudo_adaptado"]["titulo"] == "Fundamentos de VCN"


def test_patch_publicar_e_idempotente(cliente, semear_material):
    mid = semear_material(visibilidade="publicado")

    resp = cliente.patch(
        f"/api/v1/materiais/{mid}", json={"visibilidade": "publicado"}
    )

    assert resp.status_code == 200
    assert resp.json()["visibilidade"] == "publicado"


@pytest.mark.parametrize(
    "corpo",
    [
        {},
        {"conteudo_adaptado": {}},
        {"titulo": "ab"},
        {"visibilidade": "invalido"},
        {"titulo": None},
    ],
)
def test_patch_rejeita_corpo_invalido(cliente, semear_material, corpo):
    mid = semear_material()

    resp = cliente.patch(f"/api/v1/materiais/{mid}", json=corpo)

    assert resp.status_code == 422
    assert resp.json()["erro"]["codigo"] == "VALIDACAO"


def test_patch_rejeita_campo_de_conteudo(cliente, semear_material):
    mid = semear_material()

    resp = cliente.patch(f"/api/v1/materiais/{mid}", json={"conteudo_adaptado": {}})

    assert resp.status_code == 422
    assert resp.json()["erro"]["codigo"] == "VALIDACAO"


def test_patch_material_inexistente(cliente):
    resp = cliente.patch(
        "/api/v1/materiais/NAO_EXISTE", json={"visibilidade": "publicado"}
    )

    assert resp.status_code == 404
    assert resp.json()["erro"]["codigo"] == "MATERIAL_NAO_ENCONTRADO"


# ── DELETE /materiais/{id} ────────────────────────────────────────────────────


def test_delete_material_informa_falha_oci(cliente, semear_material, monkeypatch):
    mid = semear_material()
    monkeypatch.setattr(
        "app.api.v1.routers.materiais.remover_objeto", lambda _: False
    )

    resp = cliente.delete(f"/api/v1/materiais/{mid}")

    assert resp.status_code == 200
    assert resp.json()["oci_removido"] is False
    assert resp.json()["removido"] is True
    assert resp.json()["aviso"]
    assert cliente.get(f"/api/v1/materiais/{mid}").status_code == 404


def test_delete_material_remove_objeto_oci_e_vinculos(
    cliente, db_session, semear_material, monkeypatch
):
    mid = semear_material(oci_objeto_id="objeto-alvo.json")
    aluno_id = _semear_aluno(db_session)
    _vincular(db_session, aluno_id, mid)
    removidos: list[str] = []

    def _remover(objeto_id: str) -> bool:
        removidos.append(objeto_id)
        return True

    monkeypatch.setattr("app.api.v1.routers.materiais.remover_objeto", _remover)

    resp = cliente.delete(f"/api/v1/materiais/{mid}")

    assert resp.status_code == 200
    assert resp.json() == {
        "material_id": mid,
        "removido": True,
        "oci_removido": True,
    }
    assert removidos == ["objeto-alvo.json"]
    assert cliente.get(f"/api/v1/materiais/{mid}").status_code == 404
    assert (
        db_session.scalar(
            select(func.count()).select_from(VinculoDB).where(VinculoDB.material_id == mid)
        )
        == 0
    )


def test_delete_material_inexistente(cliente):
    resp = cliente.delete("/api/v1/materiais/NAO_EXISTE")

    assert resp.status_code == 404
    assert resp.json()["erro"]["codigo"] == "MATERIAL_NAO_ENCONTRADO"


# ── Serviço OCI ───────────────────────────────────────────────────────────────


def test_remover_objeto_sem_oci_configurado_retorna_false(monkeypatch):
    monkeypatch.setattr(oci, "_cliente_oci", lambda: (None, None))

    assert oci.remover_objeto("objeto.json") is False


def test_remover_objeto_trata_erro_do_cliente(monkeypatch):
    class _ClienteQueFalha:
        def delete_object(self, **_kwargs):
            raise RuntimeError("falha simulada")

    monkeypatch.setattr(oci, "_cliente_oci", lambda: (_ClienteQueFalha(), "namespace"))

    assert oci.remover_objeto("objeto.json") is False


def test_remover_objeto_devolve_true_no_sucesso(monkeypatch):
    chamadas: list[dict] = []

    class _Cliente:
        def delete_object(self, **kwargs):
            chamadas.append(kwargs)

    monkeypatch.setattr(oci, "_cliente_oci", lambda: (_Cliente(), "namespace"))

    assert oci.remover_objeto("objeto.json") is True
    assert chamadas[0]["object_name"] == "objeto.json"
    assert chamadas[0]["namespace_name"] == "namespace"
