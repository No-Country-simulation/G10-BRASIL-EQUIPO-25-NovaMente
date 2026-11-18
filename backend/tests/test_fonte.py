"""Texto-fonte do material (tabela material_fontes e app/services/fonte.py).

Nada acessa a rede: o provedor de LLM, o RAG e o OCI do job são falsos.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import Base
from app.llm import Mensagem, registrar_provedor
from app.models import ArmazenamentoOci, JobResposta
from app.models.db import MaterialDB, MaterialFonteDB
from app.rag.modelos import Trecho
from app.services import fonte, repositorio
from app.workers import job_worker

# Marcador fácil de procurar nas respostas e no log.
TEXTO = (
    "TEXTO-FONTE-RESERVADO-7f3a. O código HTTP 404 indica recurso não encontrado; "
    "o método POST cria um recurso novo e o GET busca um recurso sem alterá-lo."
)
MARCADOR = "TEXTO-FONTE-RESERVADO-7f3a"

RESPOSTA_VALIDA = json.dumps({
    "tipo": "flashcards",
    "titulo": "APIs REST",
    "introducao_contextualizada": "Revisão rápida de HTTP.",
    "itens": [
        {"frente": "GET", "verso": "Busca um recurso.", "dica_didatica": None},
        {"frente": "POST", "verso": "Cria um recurso.", "dica_didatica": None},
        {"frente": "404", "verso": "Recurso não encontrado.", "dica_didatica": None},
    ],
})


def _linhas_de_fonte(db_session) -> int:
    return db_session.execute(text("SELECT COUNT(*) FROM material_fontes")).scalar_one()


# ── Serviço ───────────────────────────────────────────────────────────────────


def test_salvar_e_ler(db_session, semear_material):
    mid = semear_material()
    assert fonte.salvar_fonte(db_session, mid, TEXTO) is True
    db_session.commit()
    assert fonte.obter_fonte(mid) == TEXTO
    linha = db_session.get(MaterialFonteDB, mid)
    assert linha.caracteres == len(TEXTO)
    datetime.fromisoformat(linha.criado_em)  # mesmo formato ISO das outras tabelas


def test_salvar_de_novo_substitui(db_session, semear_material):
    mid = semear_material()
    fonte.salvar_fonte(db_session, mid, "primeira versão do texto")
    db_session.commit()
    fonte.salvar_fonte(db_session, mid, "segunda versão")
    db_session.commit()
    assert fonte.obter_fonte(mid) == "segunda versão"
    assert db_session.get(MaterialFonteDB, mid).caracteres == len("segunda versão")
    assert _linhas_de_fonte(db_session) == 1


@pytest.mark.parametrize("vazio", [None, "", "   \n\t"])
def test_texto_vazio_ou_ausente_nao_cria_linha(db_session, semear_material, vazio):
    mid = semear_material()
    assert fonte.salvar_fonte(db_session, mid, vazio) is False
    db_session.commit()
    assert fonte.obter_fonte(mid) is None
    assert _linhas_de_fonte(db_session) == 0


def test_material_sem_fonte_devolve_none(semear_material):
    assert fonte.obter_fonte(semear_material()) is None
    assert fonte.obter_fonte("NAO_EXISTE") is None


# ── repositorio.salvar_pacote ─────────────────────────────────────────────────


def test_salvar_pacote_sem_texto_nao_grava_fonte(db_session, pacote_exemplo):
    repositorio.salvar_pacote(pacote_exemplo)
    assert repositorio.obter_pacote(pacote_exemplo.adaptacao_id) is not None
    assert _linhas_de_fonte(db_session) == 0


def test_salvar_pacote_com_texto_grava_e_substitui(pacote_exemplo):
    repositorio.salvar_pacote(pacote_exemplo, texto=TEXTO)
    assert fonte.obter_fonte(pacote_exemplo.adaptacao_id) == TEXTO
    repositorio.salvar_pacote(pacote_exemplo, texto="texto da nova geração")
    assert fonte.obter_fonte(pacote_exemplo.adaptacao_id) == "texto da nova geração"


def test_falha_na_fonte_nao_apaga_o_pacote_nem_loga_o_texto(pacote_exemplo, monkeypatch, caplog):
    def quebra(*_a, **_k):
        raise RuntimeError(f"falha simulada com os parâmetros {TEXTO}")

    monkeypatch.setattr(fonte, "salvar_fonte", quebra)
    with caplog.at_level(logging.WARNING):
        repositorio.salvar_pacote(pacote_exemplo, texto=TEXTO)
    assert repositorio.obter_pacote(pacote_exemplo.adaptacao_id) is not None
    assert fonte.obter_fonte(pacote_exemplo.adaptacao_id) is None
    assert "RuntimeError" in caplog.text
    assert MARCADOR not in caplog.text


# ── Job ───────────────────────────────────────────────────────────────────────


class _ModeloFalso:
    nome = "falso"

    def gerar(self, mensagens: list[Mensagem], *, timeout_segundos: float) -> str:
        return RESPOSTA_VALIDA


@pytest.fixture
def job_falso(monkeypatch):
    """Provedor, RAG e OCI falsos; devolve uma função que roda o worker."""
    from app.rag import servico
    from app.services import oci

    registrar_provedor("falso", _ModeloFalso)
    monkeypatch.setattr(settings, "llm_provider", "falso")

    def indexar(**kw):
        kw["on_etapa"]("chunking")
        kw["on_etapa"]("embeddings")

    monkeypatch.setattr(servico, "indexar_documento", indexar)
    monkeypatch.setattr(
        servico, "recuperar",
        lambda **kw: [Trecho(texto=TEXTO, indice=0, relevancia=0.9, documento_id=kw["documento_id"])],
    )
    monkeypatch.setattr(
        oci, "fazer_upload",
        lambda pacote, objeto_id: ArmazenamentoOci(bucket="teste", objeto_id=objeto_id, status_upload="falha"),
    )

    def rodar(job_id: str = "JOB_FONTE") -> JobResposta:
        agora = datetime.now(timezone.utc).isoformat()
        repositorio.salvar_job(JobResposta(job_id=job_id, status="queued", iniciado_em=agora, atualizado_em=agora))
        job_worker._executar(
            job_id, f"doc_{job_id}", "APIs REST", TEXTO, "texto", None, None,
            "Iniciante", "Flashcards", "Geral", "Didatico",
        )
        return repositorio.obter_job(job_id)

    return rodar


def test_job_bem_sucedido_grava_a_fonte(job_falso):
    job = job_falso()
    assert job.status == "succeeded"
    assert fonte.obter_fonte(job.adaptacao_id) == TEXTO


def test_falha_na_fonte_nao_derruba_o_job(job_falso, monkeypatch, caplog):
    def quebra(*_a, **_k):
        raise RuntimeError(f"falha simulada {TEXTO}")

    monkeypatch.setattr(fonte, "salvar_fonte", quebra)
    with caplog.at_level(logging.WARNING):
        job = job_falso()
    assert job.status == "succeeded"
    assert repositorio.obter_pacote(job.adaptacao_id) is not None
    assert fonte.obter_fonte(job.adaptacao_id) is None
    assert MARCADOR not in caplog.text


# ── Remoção do material ───────────────────────────────────────────────────────


def test_delete_do_material_apaga_a_fonte(cliente, db_session, pacote_exemplo, monkeypatch):
    monkeypatch.setattr("app.api.v1.routers.materiais.remover_objeto", lambda _: True)
    repositorio.salvar_pacote(pacote_exemplo, texto=TEXTO)
    mid = pacote_exemplo.adaptacao_id
    assert fonte.obter_fonte(mid) == TEXTO

    assert cliente.delete(f"/api/v1/materiais/{mid}").status_code == 200
    assert fonte.obter_fonte(mid) is None
    assert _linhas_de_fonte(db_session) == 0


def test_cascade_vale_para_delete_direto_no_banco(db_session, semear_material):
    mid = semear_material()
    fonte.salvar_fonte(db_session, mid, TEXTO)
    db_session.commit()
    db_session.execute(text("DELETE FROM materiais WHERE material_id = :m"), {"m": mid})
    db_session.commit()
    assert _linhas_de_fonte(db_session) == 0


def test_fonte_sem_material_e_recusada(db_session):
    from sqlalchemy.exc import IntegrityError

    fonte.salvar_fonte(db_session, "NAO_EXISTE", TEXTO)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


# ── Privacidade ───────────────────────────────────────────────────────────────


def test_nenhuma_rota_devolve_o_texto_fonte(cliente, db_session, pacote_exemplo, semear_aluno, vincular):
    repositorio.salvar_pacote(pacote_exemplo, texto=TEXTO)
    mid = pacote_exemplo.adaptacao_id
    assert fonte.obter_fonte(mid) == TEXTO  # a fonte existe; o teste não passa por ausência
    material = db_session.get(MaterialDB, mid)
    material.visibilidade = "publicado"
    db_session.commit()
    aluno = semear_aluno()
    vincular(aluno, mid)

    rotas = [
        "/api/v1/materiais",
        f"/api/v1/materiais/{mid}",
        "/api/v1/adaptacoes",
        f"/api/v1/adaptacoes/{mid}",
        f"/api/v1/adaptacoes/{mid}/download",
        f"/api/v1/adaptacoes/{mid}/exportacao?formato=md",
        f"/api/v1/adaptacoes/{mid}/exportacao?formato=csv",
        f"/api/v1/aluno/materiais?aluno_id={aluno}",
        f"/api/v1/aluno/materiais/{mid}?aluno_id={aluno}",
        f"/api/v1/alunos/{aluno}/materiais",
    ]
    for rota in rotas:
        resp = cliente.get(rota)
        assert resp.status_code == 200, rota
        assert MARCADOR not in resp.text, rota

    resp = cliente.patch(f"/api/v1/materiais/{mid}", json={"titulo": "Novo título"})
    assert resp.status_code == 200
    assert MARCADOR not in resp.text


# ── Banco antigo ──────────────────────────────────────────────────────────────


def test_banco_antigo_sobe_e_ganha_a_tabela_vazia(tmp_path, monkeypatch):
    """Arquivo criado antes da tabela nova: a subida cria material_fontes e mantém os dados."""
    from fastapi.testclient import TestClient

    from app import main

    antigo = create_engine(f"sqlite:///{tmp_path / 'antigo.db'}")
    tabelas = [t for t in Base.metadata.sorted_tables if t.name != "material_fontes"]
    Base.metadata.create_all(bind=antigo, tables=tabelas)
    agora = datetime.now(timezone.utc).isoformat()
    with Session(antigo) as s:
        s.add(MaterialDB(
            material_id="M_ANTIGO", adaptacao_id="M_ANTIGO", titulo="T", documento_titulo="D",
            documento_origem="texto", perfil="Iniciante", formato="Flashcards", nivel="Didatico",
            nicho="Geral", tempo_estimado_minutos=5, ancoragem_score=0.9, status_upload="concluido",
            conceitos_chave_json="[]", oci_objeto_id="o.json", pacote_json="{}",
            criado_em=agora, atualizado_em=agora,
        ))
        s.commit()
    assert "material_fontes" not in inspect(antigo).get_table_names()

    monkeypatch.setattr(main, "engine", antigo)
    with TestClient(main.app) as c:
        assert c.get("/api/v1/health").status_code == 200

    assert "material_fontes" in inspect(antigo).get_table_names()
    with antigo.connect() as conn:
        conn.execute(text("PRAGMA foreign_keys=ON"))
        assert conn.execute(text("SELECT COUNT(*) FROM material_fontes")).scalar_one() == 0
        assert conn.execute(text("SELECT COUNT(*) FROM materiais")).scalar_one() == 1
        # A tabela nova aceita fonte do material antigo e some com ele.
        conn.execute(text(
            "INSERT INTO material_fontes (material_id, texto, caracteres, criado_em) "
            "VALUES ('M_ANTIGO', 'texto', 5, :agora)"
        ), {"agora": agora})
        conn.execute(text("DELETE FROM materiais WHERE material_id = 'M_ANTIGO'"))
        assert conn.execute(text("SELECT COUNT(*) FROM material_fontes")).scalar_one() == 0
        conn.commit()
    antigo.dispose()
