"""Limpeza do índice do Chroma: ao fim de cada job e na varredura da subida.

O pipeline é trocado por um falso que indexa de verdade (embedding falso e
Chroma temporário) e depois conclui, falha, cancela ou estoura o prazo; assim
o teste mede o worker, sem depender do LLM.
"""

from __future__ import annotations

import logging

import pytest
from fastapi.testclient import TestClient
from ulid import ULID

from app.core.config import settings
from app.models import (
    AdaptacaoPacote,
    ArmazenamentoOci,
    AvaliacaoQualidade,
    ConteudoFlashcards,
    DocumentoRef,
    FlashcardItem,
    JobResposta,
    MetadadosAdaptacao,
)
from app.rag import armazenamento, servico
from app.services import limpeza_indice, pipeline, repositorio
from app.workers import job_worker

AGORA = "2026-11-16T12:00:00+00:00"
TEXTO = "\n\n".join(
    ["O protocolo HTTP define métodos como GET, POST, PUT e DELETE para manipular recursos."] * 6
)


def _novo_job(status: str = "queued") -> str:
    job_id = str(ULID())
    repositorio.salvar_job(
        JobResposta(job_id=job_id, status=status, iniciado_em=AGORA, atualizado_em=AGORA)
    )
    return job_id


def _pacote() -> AdaptacaoPacote:
    return AdaptacaoPacote(
        adaptacao_id=str(ULID()),
        criado_em=AGORA,
        documento=DocumentoRef(titulo="Manual de HTTP", origem="texto"),
        metadados=MetadadosAdaptacao(
            perfil_aplicado="Desenvolvedor",
            formato_gerado="Flashcards",
            nivel_detalhe_aplicado="Tecnico",
            nicho_setor_aplicado="Geral",
            tempo_estimado_estudo_minutos=5,
            conceitos_chave=["HTTP"],
        ),
        conteudo_adaptado=ConteudoFlashcards(
            titulo="Cartões",
            introducao_contextualizada="Intro.",
            itens=[FlashcardItem(frente=f"F{i}", verso=f"V{i}") for i in range(3)],
        ),
        avaliacao_qualidade=AvaliacaoQualidade(ancoragem_fonte_score=0.9, clareza_pedagogica="Alta"),
        armazenamento_oci=ArmazenamentoOci(bucket="b", objeto_id="o.json", status_upload="falha"),
    )


def _rodar(job_id: str, texto: str = TEXTO) -> JobResposta:
    job_worker._executar(
        job_id, f"doc_{job_id}", "Manual de HTTP", texto, "texto", None, None,
        "Desenvolvedor", "Flashcards", "Geral", "Tecnico",
    )
    return repositorio.obter_job(job_id)


@pytest.fixture
def pipeline_falso(monkeypatch):
    """Indexa de verdade e depois segue o ``cenario`` escolhido pelo teste."""
    estado = {"cenario": "sucesso", "indexou": False, "pacote": None}

    def executar(**kw):
        documento_id = kw["documento_id"]
        avisar = kw["on_progresso"]
        servico.indexar_documento(
            documento_id=documento_id, titulo=kw["titulo"], texto=kw["texto"],
            on_etapa=lambda etapa: avisar(etapa, 30, ""),
        )
        estado["indexou"] = armazenamento.existe_documento(documento_id)
        cenario = estado["cenario"]
        if cenario == "falha":
            raise RuntimeError("O serviço de IA está indisponível no momento. Tente novamente em instantes.")
        if cenario == "cancelado":
            job_worker.solicitar_cancelamento(documento_id.removeprefix("doc_"))
        if cenario == "prazo":
            monkeypatch.setattr(settings, "job_timeout_segundos", -1)
        avisar("gerando", 65, "Redigindo material didático...")
        estado["pacote"] = _pacote()
        avisar("armazenando", 100, "Salvo no OCI.")
        return estado["pacote"]

    monkeypatch.setattr(pipeline, "executar_pipeline", executar)
    return estado


# ── Limpeza no fim do job ─────────────────────────────────────────────────────


@pytest.mark.usefixtures("embedding_falso", "chroma_temporario")
@pytest.mark.parametrize(
    "cenario,status,mensagem",
    [
        ("sucesso", "succeeded", "Material gerado com sucesso."),
        ("falha", "failed", "O serviço de IA está indisponível no momento. Tente novamente em instantes."),
        ("cancelado", "cancelled", "Geração cancelada pelo usuário."),
        ("prazo", "failed", "A geração excedeu o tempo limite de"),
    ],
)
def test_job_terminado_nao_deixa_linhas_do_documento(pipeline_falso, cenario, status, mensagem):
    pipeline_falso["cenario"] = cenario
    job_id = _novo_job()
    job = _rodar(job_id)
    assert job.status == status
    assert job.mensagem.startswith(mensagem)
    assert pipeline_falso["indexou"]  # o documento chegou a ser indexado
    assert not armazenamento.existe_documento(f"doc_{job_id}")
    assert armazenamento.documentos_indexados() == {}


@pytest.mark.usefixtures("embedding_falso", "chroma_temporario")
def test_limpeza_so_roda_depois_do_estado_final_salvo(pipeline_falso, monkeypatch):
    remover_real = armazenamento.remover_documento
    vistos = []

    def remover_espiando(documento_id):
        vistos.append(repositorio.obter_job(documento_id.removeprefix("doc_")).status)
        return remover_real(documento_id)

    monkeypatch.setattr(armazenamento, "remover_documento", remover_espiando)
    _rodar(_novo_job())
    assert vistos == ["succeeded"]


@pytest.mark.usefixtures("embedding_falso", "chroma_temporario")
def test_falha_antes_de_indexar_nao_deixa_nada_nem_quebra(pipeline_falso, caplog):
    job_id = _novo_job()
    with caplog.at_level(logging.WARNING, logger="app.services.limpeza_indice"):
        job = _rodar(job_id, texto="curto demais")
    assert job.status == "failed"
    assert not pipeline_falso["indexou"]
    assert armazenamento.documentos_indexados() == {}
    assert [r for r in caplog.records if r.name == "app.services.limpeza_indice"] == []


@pytest.mark.usefixtures("embedding_falso", "chroma_temporario")
def test_erro_ao_apagar_nao_muda_o_job_e_gera_aviso(pipeline_falso, monkeypatch, caplog):
    def quebra(_documento_id):
        raise RuntimeError("disco cheio")

    monkeypatch.setattr(armazenamento, "remover_documento", quebra)
    job_id = _novo_job()
    with caplog.at_level(logging.WARNING, logger="app.services.limpeza_indice"):
        job = _rodar(job_id)
    assert job.status == "succeeded"
    assert job.resultado == pipeline_falso["pacote"]
    assert job.erro is None
    avisos = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert avisos == [f"Não foi possível remover o índice do documento doc_{job_id} (RuntimeError)."]


@pytest.mark.usefixtures("embedding_falso", "chroma_temporario")
def test_erro_ao_apagar_depois_de_falha_mantem_a_falha(pipeline_falso, monkeypatch):
    monkeypatch.setattr(armazenamento, "remover_documento", lambda _d: 1 / 0)
    pipeline_falso["cenario"] = "falha"
    job = _rodar(_novo_job())
    assert job.status == "failed"
    assert job.mensagem.startswith("O serviço de IA está indisponível")


def test_sem_chroma_o_job_nao_cria_a_pasta(chroma_isolado, monkeypatch):
    monkeypatch.setattr(pipeline, "executar_pipeline", lambda **_kw: _pacote())
    job = _rodar(_novo_job())
    assert job.status == "succeeded"
    assert not chroma_isolado.exists()
    assert limpeza_indice.remover_indice("doc_X") is False
    assert not chroma_isolado.exists()


# ── Varredura na subida ───────────────────────────────────────────────────────


def _indexar(documento_id: str, linhas: int = 2) -> None:
    armazenamento.salvar_trechos(documento_id, "T", [f"t{i}" for i in range(linhas)], [[1.0, 0.0]] * linhas)


@pytest.fixture
def indice_misto():
    """Órfãos do pipeline, documentos de jobs em andamento e ids que não são do pipeline."""
    orfao_sem_job = f"doc_{ULID()}"
    orfao_falhou = f"doc_{_novo_job('failed')}"
    rodando = f"doc_{_novo_job('running')}"
    na_fila = f"doc_{_novo_job('queued')}"
    ulid = str(ULID())
    alheios = ["doc-manual", "doc_123", f"doc_{ulid.lower()}", f"outro_{ulid}", ulid, f"doc_{ulid}x"]
    _indexar(orfao_sem_job, 3)
    _indexar(orfao_falhou, 2)
    for documento_id in [rodando, na_fila, *alheios]:
        _indexar(documento_id)
    return {"orfaos": [orfao_sem_job, orfao_falhou], "preservados": [rodando, na_fila, *alheios]}


@pytest.mark.usefixtures("chroma_temporario")
def test_varredura_remove_orfaos_e_preserva_o_resto(indice_misto, caplog):
    with caplog.at_level(logging.INFO, logger="app.services.limpeza_indice"):
        assert limpeza_indice.varrer_indices_orfaos() == 5
    restantes = armazenamento.documentos_indexados()
    assert set(restantes) == set(indice_misto["preservados"])
    assert not set(indice_misto["orfaos"]) & set(restantes)
    assert "5 linhas órfãs removidas (2 documentos)" in caplog.text


@pytest.mark.usefixtures("chroma_temporario")
def test_varredura_e_idempotente(indice_misto):
    assert limpeza_indice.varrer_indices_orfaos() == 5
    depois = armazenamento.documentos_indexados()
    assert limpeza_indice.varrer_indices_orfaos() == 0
    assert armazenamento.documentos_indexados() == depois


@pytest.mark.usefixtures("chroma_temporario")
def test_varredura_continua_se_um_documento_falha(indice_misto, monkeypatch, caplog):
    remover_real = armazenamento.remover_documento
    primeiro, segundo = sorted(indice_misto["orfaos"])

    def remover(documento_id):
        if documento_id == primeiro:
            raise RuntimeError("travado")
        return remover_real(documento_id)

    monkeypatch.setattr(armazenamento, "remover_documento", remover)
    with caplog.at_level(logging.WARNING, logger="app.services.limpeza_indice"):
        limpeza_indice.varrer_indices_orfaos()
    restantes = armazenamento.documentos_indexados()
    assert primeiro in restantes and segundo not in restantes
    assert f"Não foi possível remover o índice órfão {primeiro} (RuntimeError)." in caplog.text


@pytest.mark.parametrize(
    "documento_id,esperado",
    [
        (f"doc_{'0' * 26}", True),
        ("doc_01J9Z8Y7X6W5V4T3S2R1Q0P9N8", True),
        ("doc_01J9Z8Y7X6W5V4T3S2R1Q0P9NI", False),  # I não é do alfabeto Crockford
        ("doc_01j9z8y7x6w5v4t3s2r1q0p9n8", False),
        ("doc_01J9Z8Y7X6W5V4T3S2R1Q0P9N", False),
        ("doc-01J9Z8Y7X6W5V4T3S2R1Q0P9N8", False),
        ("doc_manual", False),
    ],
)
def test_reconhece_so_ids_do_pipeline(documento_id, esperado):
    assert limpeza_indice.documento_do_pipeline(documento_id) is esperado


class _ClienteQueFalha:
    def get_or_create_collection(self, *_a, **_kw):
        raise RuntimeError("chroma corrompido")


def test_varredura_com_chroma_quebrado_vira_aviso(caplog):
    armazenamento.definir_cliente(_ClienteQueFalha())
    with caplog.at_level(logging.WARNING, logger="app.services.limpeza_indice"):
        assert limpeza_indice.varrer_indices_orfaos() == 0
        assert limpeza_indice.remover_indice(f"doc_{ULID()}") is False
    assert "Varredura do índice do Chroma não executada (RuntimeError)." in caplog.text


def test_subida_continua_com_chroma_quebrado(caplog):
    from app.main import app

    armazenamento.definir_cliente(_ClienteQueFalha())
    with caplog.at_level(logging.WARNING, logger="app.services.limpeza_indice"):
        with TestClient(app) as client:
            assert client.get("/api/v1/health").status_code == 200
    assert "Varredura do índice do Chroma não executada" in caplog.text


def test_varredura_sem_pasta_nao_cria_a_pasta(chroma_isolado):
    assert limpeza_indice.varrer_indices_orfaos() == 0
    assert not chroma_isolado.exists()


def test_varredura_usa_a_pasta_configurada_quando_ela_existe(chroma_isolado):
    import chromadb

    chroma_isolado.mkdir()
    orfao = f"doc_{ULID()}"
    armazenamento.definir_cliente(chromadb.PersistentClient(path=str(chroma_isolado)))
    _indexar(orfao)
    armazenamento.definir_cliente(None)  # a varredura abre a pasta sozinha
    assert limpeza_indice.varrer_indices_orfaos() == 2
    assert orfao not in armazenamento.documentos_indexados()


@pytest.mark.usefixtures("chroma_temporario")
def test_subida_remove_orfaos_inclusive_de_jobs_interrompidos():
    from app.main import app

    interrompido = _novo_job("running")  # o processo anterior parou no meio
    _indexar(f"doc_{interrompido}")
    _indexar("doc-manual")
    with TestClient(app):
        pass
    assert repositorio.obter_job(interrompido).status == "failed"
    assert armazenamento.documentos_indexados() == {"doc-manual": 2}


def test_jobs_em_andamento_so_le():
    rodando, na_fila = _novo_job("running"), _novo_job("queued")
    _novo_job("failed")
    assert sorted(repositorio.jobs_em_andamento()) == sorted([rodando, na_fila])
    assert repositorio.obter_job(rodando).status == "running"
