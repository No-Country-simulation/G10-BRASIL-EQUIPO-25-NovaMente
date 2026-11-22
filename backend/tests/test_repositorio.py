"""Testes do repositório SQLite de jobs e pacotes (issue #55)."""

from __future__ import annotations

import os
import sqlite3
import threading
from contextlib import closing

import pytest

from app.core.config import settings
from app.models import (
    AdaptacaoPacote,
    ArmazenamentoOci,
    AvaliacaoQualidade,
    ConteudoFlashcards,
    ConteudoMarkdown,
    ConteudoQuiz,
    DocumentoRef,
    ErroJob,
    FlashcardItem,
    JobResposta,
    MetadadosAdaptacao,
    QuizItem,
)
from app.services import repositorio

AGORA = "2026-11-06T12:00:00+00:00"


def _job(job_id: str, status: str = "queued", **extra) -> JobResposta:
    return JobResposta(job_id=job_id, status=status, iniciado_em=AGORA, atualizado_em=AGORA, **extra)


def _pacote(adaptacao_id: str, conteudo, formato: str = "Flashcards") -> AdaptacaoPacote:
    return AdaptacaoPacote(
        adaptacao_id=adaptacao_id,
        criado_em=AGORA,
        documento=DocumentoRef(titulo="Manual de HTTP", origem="texto"),
        metadados=MetadadosAdaptacao(
            perfil_aplicado="Iniciante",
            formato_gerado=formato,
            nivel_detalhe_aplicado="Didatico",
            nicho_setor_aplicado="Geral",
            tempo_estimado_estudo_minutos=5,
            conceitos_chave=["HTTP"],
        ),
        conteudo_adaptado=conteudo,
        avaliacao_qualidade=AvaliacaoQualidade(ancoragem_fonte_score=0.9, clareza_pedagogica="Alta"),
        armazenamento_oci=ArmazenamentoOci(bucket="b", objeto_id=f"{adaptacao_id}.json", status_upload="falha"),
    )


FLASHCARDS = ConteudoFlashcards(
    titulo="Cartões",
    introducao_contextualizada="Intro.",
    itens=[FlashcardItem(frente=f"F{i}", verso=f"V{i}", dica_didatica="d" if i == 1 else None) for i in range(3)],
)
QUIZ = ConteudoQuiz(
    titulo="Quiz",
    introducao_contextualizada="Intro.",
    itens=[QuizItem(pergunta="P?", opcoes=["a", "b"], resposta_correta=1, explicacao="E.")],
)
MARKDOWN = ConteudoMarkdown(
    titulo="Tutorial",
    introducao_contextualizada="Intro.",
    itens="## Passo 1\n\nTexto com acentuação, \"aspas\" e emoji 🚀 para conferir a ida e volta.",
)


def _reiniciar():
    """Simula outro processo: esquece o cache de esquema e reabre o mesmo arquivo."""
    repositorio._esquema_pronto.clear()


def test_ida_e_volta_de_job():
    job = _job(
        "JOB1",
        status="failed",
        etapa_atual=None,
        etapas_concluidas=["extraindo", "chunking"],
        progresso_percentual=45,
        mensagem="falhou",
        erro=ErroJob(codigo="INTERNO", mensagem="falhou", request_id="r1"),
    )
    repositorio.salvar_job(job)
    assert repositorio.obter_job("JOB1") == job
    assert repositorio.obter_job("NAO_EXISTE") is None


@pytest.mark.parametrize(
    "conteudo,formato",
    [(FLASHCARDS, "Flashcards"), (QUIZ, "Quiz"), (MARKDOWN, "Tutorial"), (MARKDOWN, "ResumoExecutivo")],
    ids=["flashcards", "quiz", "tutorial", "resumo"],
)
def test_ida_e_volta_de_pacote(conteudo, formato):
    pacote = _pacote(f"PAC_{formato}", conteudo, formato)
    repositorio.salvar_pacote(pacote)
    lido = repositorio.obter_pacote(pacote.adaptacao_id)
    assert lido == pacote
    assert type(lido.conteudo_adaptado) is type(conteudo)
    assert repositorio.obter_pacote("NAO_EXISTE") is None


def test_job_com_resultado_guarda_o_pacote_completo():
    pacote = _pacote("PAC_JOB", FLASHCARDS)
    job = _job("JOB_OK", status="succeeded", adaptacao_id=pacote.adaptacao_id, resultado=pacote)
    repositorio.salvar_job(job)
    assert repositorio.obter_job("JOB_OK").resultado == pacote


def test_dados_persistem_depois_de_reiniciar():
    repositorio.salvar_job(_job("JOB_P", status="succeeded"))
    repositorio.salvar_pacote(_pacote("PAC_P", QUIZ, "Quiz"))
    _reiniciar()
    assert repositorio.obter_job("JOB_P").status == "succeeded"
    assert [p.adaptacao_id for p in repositorio.listar_pacotes()] == ["PAC_P"]


def test_iniciar_marca_em_andamento_como_failed_e_preserva_os_outros():
    for status in ["queued", "running", "succeeded", "failed", "cancelled"]:
        repositorio.salvar_job(_job(f"JOB_{status}", status=status, etapa_atual="gerando"))
    _reiniciar()
    repositorio.iniciar()

    for status in ["queued", "running"]:
        job = repositorio.obter_job(f"JOB_{status}")
        assert job.status == "failed"
        assert job.etapa_atual is None
        assert job.mensagem == repositorio.MENSAGEM_INTERROMPIDO
        assert job.erro.codigo == "INTERNO"
        assert job.erro.mensagem == repositorio.MENSAGEM_INTERROMPIDO
        assert job.erro.request_id
        assert job.atualizado_em != AGORA
    for status in ["succeeded", "failed", "cancelled"]:
        job = repositorio.obter_job(f"JOB_{status}")
        assert job.status == status
        assert job.etapa_atual == "gerando"


def test_ttl_expira_job_e_nao_pacote(monkeypatch):
    relogio = [1_000_000.0]
    monkeypatch.setattr(repositorio.time, "time", lambda: relogio[0])
    repositorio.salvar_job(_job("JOB_TTL"), ttl_segundos=60)
    repositorio.salvar_pacote(_pacote("PAC_TTL", FLASHCARDS))

    relogio[0] += 59
    assert repositorio.obter_job("JOB_TTL") is not None
    repositorio.salvar_job(_job("JOB_TTL", status="running"), ttl_segundos=60)  # renova o prazo
    relogio[0] += 59
    assert repositorio.obter_job("JOB_TTL") is not None
    relogio[0] += 2
    assert repositorio.obter_job("JOB_TTL") is None
    assert repositorio.obter_pacote("PAC_TTL") is not None


def test_listar_pacotes_mantem_ordem_de_criacao():
    for i in range(5):
        repositorio.salvar_pacote(_pacote(f"PAC_{i}", FLASHCARDS))
    atualizado = _pacote("PAC_1", QUIZ, "Quiz")
    repositorio.salvar_pacote(atualizado)  # salvar de novo não muda a posição
    pacotes = repositorio.listar_pacotes()
    assert [p.adaptacao_id for p in pacotes] == [f"PAC_{i}" for i in range(5)]
    assert pacotes[1] == atualizado


def test_threads_gravando_ao_mesmo_tempo():
    erros: list[BaseException] = []
    largada = threading.Barrier(20)

    def gravar(i: int):
        try:
            largada.wait()
            for passo in range(5):
                repositorio.salvar_job(_job(f"JOB_T{i}", status="running", progresso_percentual=passo * 20))
                repositorio.obter_job(f"JOB_T{i}")
        except BaseException as exc:  # noqa: BLE001
            erros.append(exc)

    threads = [threading.Thread(target=gravar, args=(i,)) for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert erros == []
    for i in range(20):
        assert repositorio.obter_job(f"JOB_T{i}").progresso_percentual == 80


def test_banco_novo_em_pasta_que_nao_existe(tmp_path, monkeypatch):
    caminho = tmp_path / "nao" / "existe" / "novamente.sqlite3"
    monkeypatch.setattr(settings, "db_path", str(caminho))
    repositorio.salvar_job(_job("JOB_NOVO"))
    assert caminho.exists()
    with closing(sqlite3.connect(caminho)) as conexao:
        assert conexao.execute("PRAGMA user_version").fetchone()[0] == repositorio.VERSAO_ESQUEMA
        assert conexao.execute("PRAGMA journal_mode").fetchone()[0] == "wal"


def test_db_path_invalido_gera_mensagem_clara(tmp_path, monkeypatch):
    arquivo = tmp_path / "sou_um_arquivo"
    arquivo.write_text("x")
    monkeypatch.setattr(settings, "db_path", str(arquivo / "novamente.sqlite3"))
    with pytest.raises(RuntimeError) as erro:
        repositorio.salvar_job(_job("JOB_X"))
    assert str(arquivo) in str(erro.value)
    assert "DB_PATH" in str(erro.value)


def _banco_existente(caminho):
    caminho.parent.mkdir(parents=True, exist_ok=True)
    sqlite3.connect(caminho).close()


def _arquivo_sem_escrita(caminho):
    _banco_existente(caminho)
    caminho.chmod(0o444)


def _pasta_sem_escrita(caminho):
    _banco_existente(caminho)
    caminho.parent.chmod(0o555)


def _arquivo_que_nao_e_banco(caminho):
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text("isto não é um banco sqlite " * 100)


@pytest.mark.parametrize(
    "preparar,precisa_nao_root",
    [(_arquivo_sem_escrita, True), (_pasta_sem_escrita, True), (_arquivo_que_nao_e_banco, False)],
    ids=["arquivo-sem-escrita", "pasta-sem-escrita", "arquivo-nao-e-banco"],
)
def test_falha_no_primeiro_comando_vira_mensagem_clara(tmp_path, monkeypatch, preparar, precisa_nao_root):
    # O connect passa nesses casos; o erro só aparece ao criar o esquema.
    # `geteuid` não existe no Windows e as permissões POSIX não se aplicam lá.
    if precisa_nao_root and (not hasattr(os, "geteuid") or os.geteuid() == 0):
        pytest.skip("permissões de arquivo POSIX não são testáveis neste SO")
    caminho = tmp_path / "banco" / "novamente.sqlite3"
    preparar(caminho)
    monkeypatch.setattr(settings, "db_path", str(caminho))

    conexoes = []
    connect_original = sqlite3.connect

    def connect_espiao(*args, **kwargs):
        conexoes.append(connect_original(*args, **kwargs))
        return conexoes[-1]

    monkeypatch.setattr(repositorio.sqlite3, "connect", connect_espiao)
    try:
        with pytest.raises(RuntimeError) as erro:
            repositorio.salvar_job(_job("JOB_X"))
    finally:
        caminho.parent.chmod(0o755)  # permite ao pytest apagar o tmp_path

    mensagem = str(erro.value)
    assert str(caminho) in mensagem
    assert "DB_PATH" in mensagem and "permissões" in mensagem
    assert isinstance(erro.value.__cause__, sqlite3.Error)
    assert conexoes, "a conexão deveria ter sido aberta"
    with pytest.raises(sqlite3.ProgrammingError):
        conexoes[0].execute("SELECT 1")  # já fechada
