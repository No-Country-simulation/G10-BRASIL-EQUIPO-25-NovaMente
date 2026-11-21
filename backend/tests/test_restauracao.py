"""Restauração do SQLite a partir de um backup (issue #70).

Reproduz o procedimento do README: gera o backup, perde o banco, para o backend
(aqui, descarta as conexões), troca o arquivo pelo backup, remove ``-wal``/``-shm``
e sobe de novo.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.db import SessionLocal, engine
from app.models import AlunoCriacao, JobResposta
from app.services import alunos, repositorio
from app.services.backup import aplicar_retencao, gerar_backup, listar_backups

AGORA = "2026-11-20T12:00:00+00:00"


@pytest.fixture
def banco_unico(monkeypatch):
    """DB_PATH e catálogo no mesmo arquivo, como em produção."""
    arquivo = Path(engine.url.database)
    monkeypatch.setattr(settings, "db_path", str(arquivo))
    return arquivo


def _semear(pacote) -> dict:
    repositorio.salvar_pacote(pacote)  # tabela pacotes + catálogo de materiais
    job = JobResposta(
        job_id="job-restauracao",
        status="succeeded",
        progresso_percentual=100,
        iniciado_em=AGORA,
        atualizado_em=AGORA,
        adaptacao_id=pacote.adaptacao_id,
    )
    repositorio.salvar_job(job, ttl_segundos=3600)
    with SessionLocal() as sessao:
        aluno = alunos.criar_aluno(sessao, AlunoCriacao(nome="Ana Souza", email="ana@exemplo.com"))
        alunos.adicionar_vinculo(sessao, aluno.aluno_id, pacote.adaptacao_id)
    return {"aluno_id": aluno.aluno_id, "material_id": pacote.adaptacao_id, "job_id": job.job_id}


def _perder_o_banco(arquivo: Path) -> None:
    engine.dispose()  # o backend parou: nenhuma conexão aberta
    repositorio._esquema_pronto.clear()  # processo novo: o esquema é conferido de novo
    for sufixo in ("", "-wal", "-shm"):
        Path(f"{arquivo}{sufixo}").unlink(missing_ok=True)
    assert not arquivo.exists()


def _restaurar(backup: Path, arquivo: Path) -> None:
    shutil.copy2(backup, arquivo)
    for sufixo in ("-wal", "-shm"):  # sobras do banco antigo não valem para o restaurado
        Path(f"{arquivo}{sufixo}").unlink(missing_ok=True)


def test_restauracao_recupera_jobs_materiais_alunos_e_vinculos(banco_unico, pacote_exemplo, tmp_path):
    ids = _semear(pacote_exemplo)
    backup = gerar_backup(banco_unico, tmp_path / "backups").arquivo

    _perder_o_banco(banco_unico)
    _restaurar(backup, banco_unico)

    from app.main import app

    with TestClient(app) as cliente:
        assert cliente.get("/api/v1/health").json()["banco"] == "ok"

        materiais = cliente.get("/api/v1/materiais").json()
        assert [m["material_id"] for m in materiais["itens"]] == [ids["material_id"]]
        detalhe = cliente.get(f"/api/v1/materiais/{ids['material_id']}")
        assert detalhe.status_code == 200
        assert detalhe.json()["pacote"] == pacote_exemplo.model_dump(mode="json")

        lista_alunos = cliente.get("/api/v1/alunos").json()
        assert [a["aluno_id"] for a in lista_alunos["itens"]] == [ids["aluno_id"]]
        assert lista_alunos["itens"][0]["email"] == "ana@exemplo.com"

        vinculos = cliente.get(f"/api/v1/alunos/{ids['aluno_id']}/materiais").json()
        assert [v["material_id"] for v in vinculos["itens"]] == [ids["material_id"]]

        job = cliente.get(f"/api/v1/jobs/{ids['job_id']}")
        assert job.status_code == 200
        assert job.json()["status"] == "succeeded"

    assert repositorio.obter_pacote(ids["material_id"]) is not None  # tabela legada de pacotes


def test_sem_restaurar_o_banco_perdido_sobe_vazio(banco_unico, pacote_exemplo, tmp_path):
    """Contraprova: sem a restauração, o backend sobe e atende, mas sem os dados."""
    ids = _semear(pacote_exemplo)
    _perder_o_banco(banco_unico)

    from app.main import app

    with TestClient(app) as cliente:
        assert cliente.get("/api/v1/health").json()["banco"] == "ok"
        assert cliente.get("/api/v1/materiais").json()["itens"] == []
        assert cliente.get("/api/v1/alunos").json()["itens"] == []
        assert cliente.get(f"/api/v1/jobs/{ids['job_id']}").status_code == 404


def test_backup_e_restauracao_de_ponta_a_ponta_com_retencao(banco_unico, pacote_exemplo, tmp_path):
    ids = _semear(pacote_exemplo)
    pasta = tmp_path / "backups"
    from datetime import datetime, timedelta, timezone

    base = datetime(2026, 11, 20, 3, 0, 0, tzinfo=timezone.utc)
    for dia in range(4):
        gerar_backup(banco_unico, pasta, momento=base + timedelta(days=dia))
        aplicar_retencao(pasta, 2)

    restantes = listar_backups(pasta)
    assert [p.name for p in restantes] == ["novamente-20261122-030000.db", "novamente-20261123-030000.db"]

    _perder_o_banco(banco_unico)
    _restaurar(restantes[-1], banco_unico)

    from app.main import app

    with TestClient(app) as cliente:
        vinculos = cliente.get(f"/api/v1/alunos/{ids['aluno_id']}/materiais").json()
        assert [v["material_id"] for v in vinculos["itens"]] == [ids["material_id"]]
