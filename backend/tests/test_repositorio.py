"""Testes do repositório PostgreSQL de jobs e pacotes (issue #55)."""

from __future__ import annotations

import threading

import psycopg
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
    """Simula outro processo: fecha o pool e esquece o cache de esquema."""
    repositorio.encerrar()
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


def _versoes_e_tabelas() -> tuple[list[int], set[str]]:
    with psycopg.connect(settings.database_url) as conexao:
        versoes = [v for (v,) in conexao.execute("SELECT versao FROM schema_version ORDER BY versao")]
        tabelas = {
            t for (t,) in conexao.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = current_schema()"
            )
        }
    return versoes, tabelas


def test_esquema_criado_do_zero_e_idempotente(banco_isolado):
    assert banco_isolado, "o teste precisa de DATABASE_URL"
    repositorio.salvar_job(_job("JOB_NOVO"))  # primeira operação cria o esquema, sem iniciar()
    assert _versoes_e_tabelas() == ([repositorio.VERSAO_ESQUEMA], {"schema_version", "jobs", "pacotes"})

    _reiniciar()
    repositorio.iniciar()
    repositorio.salvar_pacote(_pacote("PAC_NOVO", FLASHCARDS))
    assert _versoes_e_tabelas() == ([repositorio.VERSAO_ESQUEMA], {"schema_version", "jobs", "pacotes"})
    assert repositorio.obter_job("JOB_NOVO") is not None


def test_database_url_ausente_gera_mensagem_clara(monkeypatch):
    repositorio.encerrar()
    monkeypatch.setattr(settings, "database_url", "")
    for operacao in (repositorio.iniciar, lambda: repositorio.obter_job("X")):
        with pytest.raises(RuntimeError, match="DATABASE_URL não definida") as erro:
            operacao()
        assert "postgresql://" in str(erro.value)  # traz a dica de configuração


@pytest.mark.parametrize(
    "url",
    [
        "postgresql://usuario:SenhaSecreta123@host-inexistente.invalid:5432/banco?connect_timeout=2",
        "host=host-inexistente.invalid password=SenhaSecreta123 connect_timeout=2",
        "isto não é uma url password=SenhaSecreta123",
        "postgresql://ana:SenhaSecreta123@db.local:abc/novamente",
        "postgresql://ana:Senha@Secreta123@db.local:abc/novamente",
        "postgresql://ana:SenhaSecreta123@[::1/novamente",
        "postgresql://ana:Senha/Secreta123@host-inexistente.invalid:5432/banco?connect_timeout=2",
    ],
    ids=[
        "url-host-inexistente", "conninfo-host-inexistente", "lixo",
        "porta-invalida", "senha-com-arroba", "ipv6-invalido", "senha-com-barra",
    ],
)
def test_database_url_invalida_gera_mensagem_clara_sem_senha(monkeypatch, url):
    repositorio.encerrar()
    monkeypatch.setattr(repositorio, "POOL_TIMEOUT_ABERTURA", 1)  # não esperar os 10 s de produção
    monkeypatch.setattr(settings, "database_url", url)
    with pytest.raises(RuntimeError) as erro:
        repositorio.salvar_job(_job("JOB_X"))
    mensagem = str(erro.value)
    assert "DATABASE_URL" in mensagem
    assert "Secreta123" not in mensagem  # cobre também a senha com '@'
    assert erro.value.__cause__ is None  # a exceção original (que poderia ter a URL) não é encadeada


@pytest.mark.parametrize(
    "url",
    [
        "postgresql://ana:Senha@Secreta123@db.local:5432/novamente",
        "postgresql://ana:Senha/Secreta123@db.local:5432/novamente",
        "postgresql://ana:SenhaSecreta123@db.local:abc/novamente",
        "postgresql://ana:SenhaSecreta123@[::1/novamente",
        "isto não é uma url password=SenhaSecreta123",
    ],
    ids=["senha-com-arroba", "senha-com-barra", "porta-invalida", "ipv6-invalido", "lixo"],
)
def test_url_malformada_e_recusada_antes_do_pool(monkeypatch, caplog, url):
    caplog.set_level("WARNING")  # todos os loggers, inclusive psycopg.pool
    repositorio.encerrar()
    monkeypatch.setattr(repositorio, "POOL_TIMEOUT_ABERTURA", 1)
    monkeypatch.setattr(settings, "database_url", url)
    with pytest.raises(RuntimeError) as erro:
        repositorio.salvar_job(_job("JOB_X"))
    mensagem = str(erro.value)
    assert mensagem.startswith("DATABASE_URL malformada (")
    assert "codifique-os na URL: %40, %2F" in mensagem
    assert erro.value.__cause__ is None
    for trecho in ("Senha", "Secreta123"):
        assert trecho not in mensagem
        assert trecho not in caplog.text


def test_url_valida_com_host_inexistente_nao_e_bloqueada(monkeypatch, caplog):
    caplog.set_level("WARNING")
    repositorio.encerrar()
    monkeypatch.setattr(repositorio, "POOL_TIMEOUT_ABERTURA", 1)
    monkeypatch.setattr(
        settings, "database_url",
        "postgresql://ana:Sen%40ha%2FSecreta123@host-inexistente.invalid:5432/banco?connect_timeout=2",
    )
    with pytest.raises(RuntimeError, match="Não foi possível conectar") as erro:
        repositorio.salvar_job(_job("JOB_X"))
    assert "Secreta123" not in str(erro.value)
    assert "Secreta123" not in caplog.text


@pytest.mark.parametrize(
    "url",
    [
        "postgresql://ana:s3gr3do@db.local:5432/novamente",
        "postgresql://ana:Sen%40ha%2Fx@db.local:5432/novamente",
        "postgresql://ana:s3gr3do@db.local:5432/novamente?options=-c%20search_path%3Dteste_x",
        "postgresql://db.local/novamente",
        "postgresql:///novamente?host=/var/run/postgresql",
        "postgresql://ana:s3gr3do@h1:5432,h2:5433/novamente",
        "host=db.local user=ana password=Sen@ha/x dbname=novamente",
    ],
    ids=["simples", "codificada", "options", "sem-senha", "socket", "varios-hosts", "key-value"],
)
def test_validacao_aceita_urls_validas(url):
    repositorio._validar_url(url)  # não levanta


def test_mascarar_url():
    assert (
        repositorio.mascarar_url("postgresql://ana:s3gr3do@db.local:5432/novamente")
        == "postgresql://ana:***@db.local:5432/novamente"
    )
    assert repositorio.mascarar_url("host=db password=s3gr3do user=ana") == "host=db password=*** user=ana"
    assert repositorio.mascarar_url("postgresql://db.local/novamente") == "postgresql://db.local/novamente"


@pytest.mark.parametrize(
    "url,esperado",
    [
        ("postgresql://ana:s3gr3do@db.local:abc/novamente", "postgresql://ana:***@db.local:abc/novamente"),
        ("postgresql://ana:p@ss@db.local:abc/novamente", "postgresql://ana:***@db.local:abc/novamente"),
        ("postgresql://ana:s3gr3do@[::1/novamente", "postgresql://ana:***@[::1/novamente"),
        ("postgresql://ana:p@ss@db.local:5432/novamente", "postgresql://ana:***@db.local:5432/novamente"),
        ("postgresql://ana:Sen/ha@db.local:5432/novamente", "postgresql://ana:***@db.local:5432/novamente"),
    ],
    ids=["porta-invalida", "senha-com-arroba-porta-invalida", "ipv6-invalido", "senha-com-arroba", "senha-com-barra"],
)
def test_mascarar_url_quando_urlsplit_falha(url, esperado):
    mascarada = repositorio.mascarar_url(url)
    assert mascarada == esperado
    assert "s3gr3do" not in mascarada and "p@ss" not in mascarada and "Sen/ha" not in mascarada
