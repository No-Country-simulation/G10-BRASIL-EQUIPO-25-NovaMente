"""Testes da política de esquema do catálogo (versão + impressão digital)."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

import pytest
from sqlalchemy import Column, Index, Integer, MetaData, Table, Text, create_engine, text
from sqlalchemy.engine import make_url

from app.core import esquema
from app.core.db import Base
from app.core.esquema import (
    ESQUEMA_VERSAO,
    TABELA_METADADOS,
    EsquemaDefasadoError,
    estrutura_declarada,
    impressao_digital,
    verificar_esquema_catalogo,
)
from app.models import JobResposta
from app.services import repositorio


@pytest.fixture
def engine_temp(tmp_path):
    """Engine de um catálogo SQLite próprio, com o esquema dos modelos já criado."""
    eng = create_engine(
        f"sqlite:///{tmp_path}/catalogo.db", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=eng)
    yield eng
    eng.dispose()


def _metadados(eng):
    with eng.connect() as c:
        return c.exec_driver_sql(
            f"SELECT versao, impressao_digital, atualizado_em FROM {TABELA_METADADOS}"
        ).fetchall()


def _semear_aluno(eng, aluno_id="A1"):
    agora = datetime.now(timezone.utc).isoformat()
    with eng.begin() as c:
        c.exec_driver_sql(
            "INSERT INTO alunos (aluno_id, nome, email, status, criado_em, atualizado_em) "
            "VALUES (?, 'Ana', ?, 'ativo', ?, ?)",
            (aluno_id, f"{aluno_id.lower()}@exemplo.com", agora, agora),
        )


def _contar(eng, tabela):
    with eng.connect() as c:
        return c.exec_driver_sql(f"SELECT COUNT(*) FROM {tabela}").scalar()


def _job(job_id, status):
    agora = datetime.now(timezone.utc).isoformat()
    return JobResposta(job_id=job_id, status=status, iniciado_em=agora, atualizado_em=agora)


# ── Cenários da política ──────────────────────────────────────────────────────


def test_banco_novo_grava_versao_e_impressao_digital(engine_temp):
    verificar_esquema_catalogo(engine_temp)

    (versao, digital, _), = _metadados(engine_temp)
    assert versao == ESQUEMA_VERSAO
    assert digital == impressao_digital()


def test_banco_na_versao_atual_sobe_e_e_idempotente(engine_temp):
    verificar_esquema_catalogo(engine_temp)
    antes = _metadados(engine_temp)

    verificar_esquema_catalogo(engine_temp)
    verificar_esquema_catalogo(engine_temp)

    assert _metadados(engine_temp) == antes


def test_banco_sem_metadados_e_compativel_e_carimbado_sem_perder_dados(engine_temp):
    _semear_aluno(engine_temp)

    verificar_esquema_catalogo(engine_temp)

    (versao, digital, _), = _metadados(engine_temp)
    assert (versao, digital) == (ESQUEMA_VERSAO, impressao_digital())
    assert _contar(engine_temp, "alunos") == 1


def test_banco_sem_metadados_com_coluna_faltando_falha(engine_temp):
    _semear_aluno(engine_temp)
    with engine_temp.begin() as c:
        c.exec_driver_sql("ALTER TABLE alunos DROP COLUMN owner_id")

    with pytest.raises(EsquemaDefasadoError) as exc:
        verificar_esquema_catalogo(engine_temp)

    mensagem = str(exc.value)
    assert "owner_id" in mensagem
    assert "alunos" in mensagem
    assert "recriar" in mensagem
    assert _contar(engine_temp, "alunos") == 1
    assert _metadados(engine_temp) == []  # não carimba um banco incompatível


def test_banco_sem_metadados_com_coluna_a_mais_falha(engine_temp):
    with engine_temp.begin() as c:
        c.exec_driver_sql("ALTER TABLE materiais ADD COLUMN extra TEXT")

    with pytest.raises(EsquemaDefasadoError, match="extra"):
        verificar_esquema_catalogo(engine_temp)


def test_banco_sem_metadados_com_indice_faltando_falha(engine_temp):
    with engine_temp.begin() as c:
        c.exec_driver_sql("DROP INDEX ix_alunos_status")

    with pytest.raises(EsquemaDefasadoError, match="ix_alunos_status"):
        verificar_esquema_catalogo(engine_temp)


def test_banco_com_metadados_de_outra_versao_falha(engine_temp):
    verificar_esquema_catalogo(engine_temp, versao=1)

    with pytest.raises(EsquemaDefasadoError) as exc:
        verificar_esquema_catalogo(engine_temp, versao=2)

    mensagem = str(exc.value)
    assert "versão 1" in mensagem and "versão 2" in mensagem
    assert "recriar" in mensagem


def test_banco_com_impressao_digital_diferente_falha(engine_temp):
    verificar_esquema_catalogo(engine_temp)
    with engine_temp.begin() as c:
        c.execute(text(f"UPDATE {TABELA_METADADOS} SET impressao_digital = 'outra'"))

    with pytest.raises(EsquemaDefasadoError) as exc:
        verificar_esquema_catalogo(engine_temp)

    mensagem = str(exc.value)
    assert "ESQUEMA_VERSAO" in mensagem
    assert "impressão digital" in mensagem


def test_modelo_alterado_sem_incrementar_a_versao_e_detectado(engine_temp):
    """Banco carimbado com o esquema atual; o código passa a declarar uma coluna nova."""
    verificar_esquema_catalogo(engine_temp)

    novo = MetaData()
    for tabela in Base.metadata.tables.values():
        tabela.to_metadata(novo)
    novo.tables["alunos"].append_column(Column("telefone", Text))

    with pytest.raises(EsquemaDefasadoError, match="impressão digital"):
        verificar_esquema_catalogo(engine_temp, metadata=novo)


# ── Mensagens ─────────────────────────────────────────────────────────────────


def test_mensagem_em_portugues_com_caminho_e_passos(engine_temp):
    verificar_esquema_catalogo(engine_temp, versao=1)

    with pytest.raises(EsquemaDefasadoError) as exc:
        verificar_esquema_catalogo(engine_temp, versao=2)

    mensagem = str(exc.value)
    caminho = engine_temp.url.database
    assert caminho in mensagem
    for trecho in ("pare o backend", "mova", "suba o backend de novo", "jobs", "MVP"):
        assert trecho in mensagem
    assert isinstance(exc.value, RuntimeError)


def test_descricao_do_banco_nao_expoe_senha():
    url = make_url("postgresql://usuario:senha-secreta@host:5432/novamente")

    descricao, caminho = esquema._descrever_banco(url)

    assert "senha-secreta" not in descricao
    assert caminho is None


def test_mensagem_nao_expoe_segredos_do_ambiente(engine_temp, monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "chave-ficticia-nao-vazar")
    verificar_esquema_catalogo(engine_temp, versao=1)

    with pytest.raises(EsquemaDefasadoError) as exc:
        verificar_esquema_catalogo(engine_temp, versao=2)

    assert "chave-ficticia-nao-vazar" not in str(exc.value)


# ── Impressão digital e leitura da estrutura ──────────────────────────────────


def test_estrutura_real_de_banco_criado_pelos_modelos_bate_com_a_declarada(engine_temp):
    with engine_temp.connect() as c:
        assert esquema._diferencas(c, estrutura_declarada()) == []


def test_impressao_digital_e_estavel_e_ignora_ordem_das_colunas():
    def monta(ordem):
        md = MetaData()
        cols = {"a": Column("a", Text, primary_key=True), "b": Column("b", Integer)}
        Table("t", md, *[cols[n] for n in ordem])
        return md

    assert impressao_digital(monta("ab")) == impressao_digital(monta("ba"))
    assert impressao_digital() == impressao_digital()


def test_impressao_digital_muda_com_coluna_indice_ou_constraint():
    def monta(extra_coluna=False, indice=False, tipo=Integer):
        md = MetaData()
        t = Table("t", md, Column("a", Text, primary_key=True), Column("b", tipo))
        if extra_coluna:
            t.append_column(Column("c", Text))
        if indice:
            Index("ix_t_b", t.c.b)
        return md

    base = impressao_digital(monta())
    assert impressao_digital(monta(extra_coluna=True)) != base
    assert impressao_digital(monta(indice=True)) != base
    assert impressao_digital(monta(tipo=Text)) != base


def test_extrair_checks_lida_com_parenteses_e_aspas():
    ddl = "CREATE TABLE t (x TEXT, CONSTRAINT ck CHECK (x IN ('a)', 'b') AND (1 = 1)))"
    assert esquema._extrair_checks(ddl) == ["x IN ('a)', 'b') AND (1 = 1)"]


# ── Integração com iniciar() e preservação de dados ───────────────────────────


def _banco_defasado(engine_temp):
    _semear_aluno(engine_temp)
    with engine_temp.begin() as c:
        c.exec_driver_sql("ALTER TABLE alunos DROP COLUMN owner_id")


def test_iniciar_falha_com_catalogo_defasado_sem_apagar_jobs_nem_pacotes(
    engine_temp, monkeypatch, pacote_exemplo
):
    # Jobs e pacotes antes da verificação (arquivo de DB_PATH do teste).
    repositorio.salvar_job(_job("J-EM-ANDAMENTO", "running"))
    repositorio.salvar_job(_job("J-OK", "succeeded"))
    repositorio.salvar_pacote(pacote_exemplo)
    _banco_defasado(engine_temp)
    monkeypatch.setattr(repositorio, "engine", engine_temp)

    with pytest.raises(EsquemaDefasadoError):
        repositorio.iniciar()

    # A falha acontece antes de qualquer escrita: nem o job em andamento é alterado.
    assert repositorio.obter_job("J-EM-ANDAMENTO").status == "running"
    assert repositorio.obter_job("J-OK").status == "succeeded"
    assert repositorio.obter_pacote(pacote_exemplo.adaptacao_id) == pacote_exemplo
    assert len(repositorio.listar_pacotes()) == 1
    assert _contar(engine_temp, "alunos") == 1


@pytest.mark.parametrize("cenario", ["novo", "atual", "sem_metadados"])
def test_iniciar_preserva_jobs_e_pacotes_nos_cenarios_que_sobem(
    engine_temp, monkeypatch, pacote_exemplo, cenario
):
    repositorio.salvar_job(_job("J-OK", "succeeded"))
    repositorio.salvar_pacote(pacote_exemplo)
    monkeypatch.setattr(repositorio, "engine", engine_temp)
    if cenario == "atual":
        verificar_esquema_catalogo(engine_temp)

    repositorio.iniciar()
    repositorio.iniciar()  # subir duas vezes não muda nada

    assert len(_metadados(engine_temp)) == 1
    assert repositorio.obter_job("J-OK").status == "succeeded"
    assert repositorio.obter_pacote(pacote_exemplo.adaptacao_id) == pacote_exemplo


def test_subida_da_aplicacao_e_abortada_com_catalogo_defasado(engine_temp, monkeypatch):
    from fastapi.testclient import TestClient

    from app.main import app

    _banco_defasado(engine_temp)
    monkeypatch.setattr(repositorio, "engine", engine_temp)

    with pytest.raises(EsquemaDefasadoError, match="recriar"):
        with TestClient(app):
            pass


def test_subida_da_aplicacao_funciona_com_catalogo_atual(cliente):
    assert cliente.get("/api/v1/health").status_code == 200


def test_metadados_do_banco_dos_testes_sao_gravados_na_subida(cliente):
    from app.core.db import engine

    (versao, digital, _), = _metadados(engine)
    assert (versao, digital) == (ESQUEMA_VERSAO, impressao_digital())
