"""Teto de jobs de geração simultâneos (criar_job → 503 GERACAO_OCUPADA).

A thread do job é trocada por uma função vazia: o job fica ``queued`` no
SQLite e conta como em andamento, sem tocar LLM, RAG nem OCI.
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.limite_geracao import limitador
from app.main import app
from app.models import JobResposta
from app.services import repositorio
from app.workers import job_worker

CORPO = {
    "documento_titulo": "Manual de Teste",
    "documento_conteudo": "Texto de teste sobre APIs REST. " * 20,
    "perfil_destinatario": "Iniciante",
    "formato_saida": "Flashcards",
    "nicho_setor": "Geral",
    "nivel_detalhe": "Didatico",
}


@pytest.fixture(autouse=True)
def worker_falso(monkeypatch):
    """A thread não executa o pipeline; devolve a lista dos job_id disparados."""
    disparados: list[str] = []
    monkeypatch.setattr(job_worker, "_executar", lambda job_id, *a, **kw: disparados.append(job_id))
    monkeypatch.setattr(settings, "geracao_max_jobs_simultaneos", 2)
    limitador.limpar()
    yield disparados
    limitador.limpar()


def _criar():
    return job_worker.criar_job(
        titulo="Manual",
        texto="texto",
        origem="texto",
        nome_arquivo=None,
        tamanho_bytes=None,
        perfil="Iniciante",
        formato="Flashcards",
        nicho="Geral",
        nivel="Didatico",
    )


def _job(job_id: str, status: str) -> JobResposta:
    agora = datetime.now(timezone.utc).isoformat()
    return JobResposta(job_id=job_id, status=status, iniciado_em=agora, atualizado_em=agora)


def _aguardar_threads(disparados, esperado: int) -> None:
    for _ in range(200):
        if len(disparados) >= esperado:
            return
        threading.Event().wait(0.01)


def test_abaixo_do_teto_cria_os_jobs(worker_falso):
    primeiro, segundo = _criar(), _criar()
    _aguardar_threads(worker_falso, 2)
    assert primeiro.status == segundo.status == "queued"
    assert sorted(worker_falso) == sorted([primeiro.job_id, segundo.job_id])


def test_no_teto_recusa_com_503_e_retry_after(worker_falso):
    _criar()
    _criar()

    with pytest.raises(HTTPException) as excecao:
        _criar()

    assert excecao.value.status_code == 503
    assert excecao.value.detail["erro"]["codigo"] == "GERACAO_OCUPADA"
    assert excecao.value.detail["erro"]["mensagem"]
    retry = excecao.value.headers["Retry-After"]
    assert retry.isdigit() and int(retry) >= 1
    # A recusada não gravou job nem abriu thread.
    _aguardar_threads(worker_falso, 2)
    assert len(repositorio.jobs_em_andamento()) == 2
    assert len(worker_falso) == 2


@pytest.mark.parametrize("status", ["succeeded", "failed", "cancelled"])
def test_job_encerrado_libera_vaga(worker_falso, status):
    primeiro = _criar()
    _criar()
    repositorio.salvar_job(_job(primeiro.job_id, status))

    assert _criar().status == "queued"


def test_job_running_conta_como_em_andamento(worker_falso):
    primeiro = _criar()
    repositorio.salvar_job(_job(primeiro.job_id, "running"))
    _criar()
    with pytest.raises(HTTPException):
        _criar()


def test_job_expirado_nao_conta(worker_falso):
    # TTL negativo: o job fica gravado como queued, mas já expirado.
    repositorio.salvar_job(_job("EXPIRADO1", "queued"), ttl_segundos=-1)
    repositorio.salvar_job(_job("EXPIRADO2", "running"), ttl_segundos=-1)

    _criar()
    _criar()
    with pytest.raises(HTTPException):
        _criar()


def test_teto_acompanha_a_configuracao(worker_falso, monkeypatch):
    monkeypatch.setattr(settings, "geracao_max_jobs_simultaneos", 1)
    _criar()
    with pytest.raises(HTTPException):
        _criar()
    monkeypatch.setattr(settings, "geracao_max_jobs_simultaneos", 3)
    _criar()


def test_requisicoes_simultaneas_respeitam_o_teto(worker_falso, monkeypatch):
    monkeypatch.setattr(settings, "geracao_max_jobs_simultaneos", 3)
    tentativas = 10
    largada = threading.Barrier(tentativas)
    resultados: list[str] = []
    trava = threading.Lock()

    def requisitar():
        largada.wait()
        try:
            _criar()
            resultado = "criado"
        except HTTPException as exc:
            resultado = f"http{exc.status_code}"
        with trava:
            resultados.append(resultado)

    threads = [threading.Thread(target=requisitar) for _ in range(tentativas)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    assert resultados.count("criado") == 3
    assert resultados.count("http503") == tentativas - 3
    assert len(repositorio.jobs_em_andamento()) == 3


# ── Pela API ──────────────────────────────────────────────────────────────────


def test_api_devolve_503_com_envelope_e_retry_after(worker_falso):
    cliente = TestClient(app)
    assert cliente.post("/api/v1/adaptacoes", json=CORPO).status_code == 202
    assert cliente.post("/api/v1/adaptacoes", json=CORPO).status_code == 202

    resp = cliente.post("/api/v1/adaptacoes", json=CORPO)

    assert resp.status_code == 503
    assert resp.json()["erro"]["codigo"] == "GERACAO_OCUPADA"
    assert resp.headers["Retry-After"] == str(job_worker.RETRY_AFTER_OCUPADO_SEGUNDOS)


def test_api_503_nao_consome_o_limite_por_ip(worker_falso, monkeypatch):
    monkeypatch.setattr(settings, "geracao_limite_por_minuto", 3)
    cliente = TestClient(app)
    for _ in range(2):
        assert cliente.post("/api/v1/adaptacoes", json=CORPO).status_code == 202
    for _ in range(5):
        assert cliente.post("/api/v1/adaptacoes", json=CORPO).status_code == 503
    # Libera as vagas: a única reserva consumida é a dos dois 202.
    for job_id in repositorio.jobs_em_andamento():
        repositorio.salvar_job(_job(job_id, "succeeded"))
    assert cliente.post("/api/v1/adaptacoes", json=CORPO).status_code == 202
    assert cliente.post("/api/v1/adaptacoes", json=CORPO).status_code == 429
