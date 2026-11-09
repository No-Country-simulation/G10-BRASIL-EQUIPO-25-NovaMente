"""Repositório de jobs e pacotes de adaptação, persistido em SQLite.

O arquivo fica em ``DB_PATH`` (padrão ``/data/novamente.sqlite3``), lido a
cada operação. Jobs expiram ``JOB_TTL_SEGUNDOS`` depois da última gravação;
pacotes não expiram. Na subida, ``iniciar()`` marca como ``failed`` os jobs
que estavam em andamento quando o processo parou.

Cada operação abre e fecha a própria conexão (nada é compartilhado entre as
threads dos jobs); as escritas passam por um lock de processo e o banco usa
o modo WAL, para leituras não esperarem escritas.
"""

from __future__ import annotations

import sqlite3
import threading
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from app.models import AdaptacaoPacote, ErroJob, JobResposta

MENSAGEM_INTERROMPIDO = "A geração foi interrompida porque o servidor reiniciou. Tente novamente."

_lock = threading.Lock()
_esquema_pronto: set[str] = set()  # caminhos de arquivo cujo esquema já foi conferido


# ── Esquema e migrações ───────────────────────────────────────────────────────


def _migracao_v1(conexao: sqlite3.Connection) -> None:
    conexao.executescript(
        """
        CREATE TABLE IF NOT EXISTS jobs (
            job_id TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            dados TEXT NOT NULL,
            expira_em REAL NOT NULL,
            atualizado_em TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_jobs_expira_em ON jobs (expira_em);
        CREATE TABLE IF NOT EXISTS pacotes (
            adaptacao_id TEXT PRIMARY KEY,
            criado_em TEXT NOT NULL,
            dados TEXT NOT NULL
        );
        """
    )


# Uma função por versão, aplicadas em ordem a partir do PRAGMA user_version.
_MIGRACOES = {1: _migracao_v1}
VERSAO_ESQUEMA = max(_MIGRACOES)


def _garantir_esquema(conexao: sqlite3.Connection, chave: str) -> None:
    with _lock:
        if chave in _esquema_pronto:
            return
        conexao.execute("PRAGMA journal_mode=WAL")
        versao = conexao.execute("PRAGMA user_version").fetchone()[0]
        for proxima in range(versao + 1, VERSAO_ESQUEMA + 1):
            _MIGRACOES[proxima](conexao)
            conexao.execute(f"PRAGMA user_version = {proxima}")
        conexao.commit()
        _esquema_pronto.add(chave)


# ── Conexão ───────────────────────────────────────────────────────────────────


def _caminho() -> Path:
    from app.core.config import settings  # lido a cada chamada: os testes trocam o valor

    caminho = Path(settings.db_path).expanduser()
    try:
        caminho.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise RuntimeError(
            f"Não foi possível criar a pasta do banco de dados ({caminho.parent}). "
            "Configure DB_PATH com um caminho gravável."
        ) from exc
    return caminho


@contextmanager
def _conectar() -> Iterator[sqlite3.Connection]:
    caminho = _caminho()
    try:
        conexao = sqlite3.connect(caminho, timeout=5)
    except sqlite3.Error as exc:
        raise RuntimeError(
            f"Não foi possível abrir o banco de dados em {caminho}. "
            "Configure DB_PATH com um caminho gravável."
        ) from exc
    try:
        # O sqlite3 só toca o arquivo de verdade no primeiro comando: arquivo ou
        # pasta sem escrita e arquivo que não é banco falham aqui, não no connect.
        try:
            _garantir_esquema(conexao, str(caminho.resolve()))
        except sqlite3.Error as exc:
            raise RuntimeError(
                f"Não foi possível preparar o banco de dados em {caminho}. "
                "Configure DB_PATH com um caminho gravável e confira as permissões "
                "da pasta (ou do volume) e do arquivo."
            ) from exc
        yield conexao
    finally:
        conexao.close()


def _agora_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Jobs ──────────────────────────────────────────────────────────────────────


def _gravar_job(conexao: sqlite3.Connection, job: JobResposta, expira_em: float) -> None:
    conexao.execute(
        """
        INSERT INTO jobs (job_id, status, dados, expira_em, atualizado_em)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT (job_id) DO UPDATE SET
            status = excluded.status,
            dados = excluded.dados,
            expira_em = excluded.expira_em,
            atualizado_em = excluded.atualizado_em
        """,
        (job.job_id, job.status, job.model_dump_json(), expira_em, job.atualizado_em),
    )


def salvar_job(job: JobResposta, ttl_segundos: int = 1800) -> None:
    with _conectar() as conexao, _lock, conexao:
        _gravar_job(conexao, job, time.time() + ttl_segundos)


def obter_job(job_id: str) -> JobResposta | None:
    _purgar()
    with _conectar() as conexao:
        linha = conexao.execute("SELECT dados FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
    return JobResposta.model_validate_json(linha[0]) if linha else None


def _purgar() -> None:
    with _conectar() as conexao, _lock, conexao:
        conexao.execute("DELETE FROM jobs WHERE expira_em < ?", (time.time(),))


# ── Pacotes ───────────────────────────────────────────────────────────────────


def salvar_pacote(pacote: AdaptacaoPacote) -> None:
    with _conectar() as conexao, _lock, conexao:
        conexao.execute(
            """
            INSERT INTO pacotes (adaptacao_id, criado_em, dados) VALUES (?, ?, ?)
            ON CONFLICT (adaptacao_id) DO UPDATE SET
                criado_em = excluded.criado_em,
                dados = excluded.dados
            """,
            (pacote.adaptacao_id, pacote.criado_em, pacote.model_dump_json()),
        )


def obter_pacote(adaptacao_id: str) -> AdaptacaoPacote | None:
    with _conectar() as conexao:
        linha = conexao.execute(
            "SELECT dados FROM pacotes WHERE adaptacao_id = ?", (adaptacao_id,)
        ).fetchone()
    return AdaptacaoPacote.model_validate_json(linha[0]) if linha else None


def listar_pacotes() -> list[AdaptacaoPacote]:
    # ORDER BY rowid mantém a ordem de criação (o upsert preserva o rowid).
    with _conectar() as conexao:
        linhas = conexao.execute("SELECT dados FROM pacotes ORDER BY rowid").fetchall()
    return [AdaptacaoPacote.model_validate_json(dados) for (dados,) in linhas]


# ── Subida ────────────────────────────────────────────────────────────────────


def iniciar() -> None:
    """Prepara o banco na subida do backend.

    Garante esquema e migrações, apaga jobs expirados e marca como ``failed``
    (código INTERNO) os jobs ``queued`` ou ``running`` que o processo anterior
    deixou para trás.
    """
    from app.core.config import settings

    _purgar()
    with _conectar() as conexao, _lock, conexao:
        pendentes = conexao.execute(
            "SELECT dados FROM jobs WHERE status IN ('queued', 'running')"
        ).fetchall()
        for (dados,) in pendentes:
            job = JobResposta.model_validate_json(dados)
            interrompido = job.model_copy(
                update={
                    "status": "failed",
                    "etapa_atual": None,
                    "mensagem": MENSAGEM_INTERROMPIDO,
                    "atualizado_em": _agora_iso(),
                    "erro": ErroJob(
                        codigo="INTERNO",
                        mensagem=MENSAGEM_INTERROMPIDO,
                        request_id=str(uuid.uuid4()),
                    ),
                }
            )
            _gravar_job(conexao, interrompido, time.time() + settings.job_ttl_segundos)
