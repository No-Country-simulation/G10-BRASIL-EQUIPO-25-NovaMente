"""Testes do repositório durável em SQLite e do material criado automaticamente."""

from __future__ import annotations

import json

import pytest
from sqlalchemy import func, select, text

from app.core.db import SessionLocal
from app.models import AvaliacaoQualidade
from app.models.db import MaterialDB
from app.services import repositorio


def test_salvar_pacote_cria_material_rascunho_e_sobrevive_a_nova_sessao(
    pacote_exemplo,
):
    repositorio.salvar_pacote(pacote_exemplo)
    with SessionLocal() as nova:
        row = nova.get(MaterialDB, pacote_exemplo.adaptacao_id)
        assert row.visibilidade == "rascunho"
        assert row.formato == pacote_exemplo.metadados.formato_gerado
        assert row.ancoragem_score == pacote_exemplo.avaliacao_qualidade.ancoragem_fonte_score

        # Colunas desnormalizadas usadas pelas listagens (tarefa 3).
        assert row.titulo == pacote_exemplo.conteudo_adaptado.titulo
        assert row.documento_titulo == pacote_exemplo.documento.titulo
        assert row.documento_origem == pacote_exemplo.documento.origem
        assert row.documento_nome_arquivo == pacote_exemplo.documento.nome_arquivo
        assert row.documento_tamanho_bytes == pacote_exemplo.documento.tamanho_bytes
        assert row.perfil == pacote_exemplo.metadados.perfil_aplicado
        assert row.nivel == pacote_exemplo.metadados.nivel_detalhe_aplicado
        assert row.nicho == pacote_exemplo.metadados.nicho_setor_aplicado
        assert (
            row.tempo_estimado_minutos
            == pacote_exemplo.metadados.tempo_estimado_estudo_minutos
        )
        assert row.status_upload == pacote_exemplo.armazenamento_oci.status_upload
        assert row.oci_objeto_id == pacote_exemplo.armazenamento_oci.objeto_id
        assert json.loads(row.conceitos_chave_json) == pacote_exemplo.metadados.conceitos_chave

        from app.services import materiais

        assert materiais.pacote_de_material(row) == pacote_exemplo

    assert (
        repositorio.obter_pacote(pacote_exemplo.adaptacao_id).conteudo_adaptado
        == pacote_exemplo.conteudo_adaptado
    )


def test_salvar_pacote_preserva_titulo_e_visibilidade_editados(pacote_exemplo):
    repositorio.salvar_pacote(pacote_exemplo)
    with SessionLocal() as edicao:
        row = edicao.get(MaterialDB, pacote_exemplo.adaptacao_id)
        row.titulo = "Título editado pela interface"
        row.visibilidade = "publicado"
        edicao.commit()

    atualizado = pacote_exemplo.model_copy(
        update={
            "avaliacao_qualidade": AvaliacaoQualidade(
                ancoragem_fonte_score=0.42,
                clareza_pedagogica="Baixa",
            )
        }
    )
    repositorio.salvar_pacote(atualizado)

    with SessionLocal() as nova:
        row = nova.get(MaterialDB, pacote_exemplo.adaptacao_id)
        assert row.titulo == "Título editado pela interface"
        assert row.visibilidade == "publicado"
        assert row.ancoragem_score == 0.42
        assert nova.scalar(select(func.count()).select_from(MaterialDB)) == 1

    assert (
        repositorio.obter_pacote(pacote_exemplo.adaptacao_id)
        .avaliacao_qualidade.ancoragem_fonte_score
        == 0.42
    )


def test_listar_pacotes_ignora_pacote_json_corrompido(db_session, semear_material):
    semear_material()
    db_session.execute(text("UPDATE materiais SET pacote_json = '{'"))
    db_session.commit()

    assert repositorio.listar_pacotes() == []


def test_listar_adaptacoes_usa_colunas_quando_pacote_json_corrompido(
    cliente, db_session, semear_material
):
    material_id = semear_material(
        titulo="Resumo sem pacote",
        documento_titulo="Documento íntegro",
        formato="Quiz",
        perfil="Desenvolvedor",
        nivel="Tecnico",
        nicho="Fintech",
        tempo_estimado_minutos=7,
        ancoragem_score=0.77,
        status_upload="falha",
        conceitos_chave_json='["VCN", "Subnet"]',
        visibilidade="publicado",
    )
    db_session.execute(text("UPDATE materiais SET pacote_json = '{'"))
    db_session.commit()

    resp = cliente.get("/api/v1/adaptacoes")

    assert resp.status_code == 200
    corpo = resp.json()
    assert corpo["total"] == 1
    item = corpo["itens"][0]
    assert item["adaptacao_id"] == material_id
    assert item["documento"]["titulo"] == "Documento íntegro"
    assert item["perfil_aplicado"] == "Desenvolvedor"
    assert item["formato_gerado"] == "Quiz"
    assert item["nivel_detalhe_aplicado"] == "Tecnico"
    assert item["nicho_setor_aplicado"] == "Fintech"
    assert item["tempo_estimado_estudo_minutos"] == 7
    assert item["ancoragem_fonte_score"] == 0.77
    assert item["status_upload"] == "falha"
    assert item["conceitos_chave"] == ["VCN", "Subnet"]


def test_listar_adaptacoes_le_materiais_do_banco(cliente, semear_material):
    assert cliente.get("/api/v1/adaptacoes").json()["total"] == 0

    semear_material()

    resp = cliente.get("/api/v1/adaptacoes")
    assert resp.status_code == 200
    assert resp.json()["total"] == 1


def test_listar_adaptacoes_tolera_conceitos_chave_corrompidos(
    cliente, semear_material
):
    semear_material(conceitos_chave_json="{")

    resp = cliente.get("/api/v1/adaptacoes")

    assert resp.status_code == 200
    assert resp.json()["itens"][0]["conceitos_chave"] == []


@pytest.mark.parametrize(
    "rota",
    [
        "/api/v1/adaptacoes/{id}",
        "/api/v1/adaptacoes/{id}/download",
        "/api/v1/adaptacoes/{id}/exportacao?formato=md",
    ],
)
def test_rotas_de_leitura_de_adaptacao_com_pacote_corrompido_retornam_500(
    cliente, db_session, semear_material, rota
):
    adaptacao_id = semear_material()
    db_session.execute(text("UPDATE materiais SET pacote_json = '{'"))
    db_session.commit()

    resp = cliente.get(rota.format(id=adaptacao_id))

    assert resp.status_code == 500
    erro = resp.json()["erro"]
    assert erro["codigo"] == "INTERNO"
    assert erro["request_id"]
    assert "Pacote de adaptação corrompido." in erro["mensagem"]


def test_obter_pacote_inexistente_continua_none(db_session):
    assert repositorio.obter_pacote("NAO_EXISTE") is None


def test_obter_pacote_corrompido_levanta_excecao_dedicada(
    db_session, semear_material
):
    adaptacao_id = semear_material()
    db_session.execute(text("UPDATE materiais SET pacote_json = '{'"))
    db_session.commit()

    with pytest.raises(repositorio.PacoteCorrompido) as excinfo:
        repositorio.obter_pacote(adaptacao_id)

    assert excinfo.value.adaptacao_id == adaptacao_id
