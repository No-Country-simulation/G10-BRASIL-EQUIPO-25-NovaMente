"""Repositório de jobs e pacotes de adaptação, persistido em PostgreSQL.

A URL vem de ``DATABASE_URL``, lida a cada operação. Jobs expiram
``JOB_TTL_SEGUNDOS`` depois da última gravação; pacotes não expiram. Na
subida, ``iniciar()`` marca como ``failed`` os jobs que estavam em andamento
quando o processo parou. O modelo sempre é lido da coluna ``dados`` (JSONB);
as colunas de data servem para purga e ordenação.

O acesso usa um ``ConnectionPool`` (psycopg 3, síncrono) aberto sob demanda;
as threads dos jobs pegam conexões dele, sem lock de escrita próprio.
"""

from __future__ import annotations

import re
import threading
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from urllib.parse import urlsplit, urlunsplit

import psycopg
from psycopg.conninfo import conninfo_to_dict
from psycopg_pool import ConnectionPool

from app.models import AdaptacaoPacote, ErroJob, JobResposta

MENSAGEM_INTERROMPIDO = "A geração foi interrompida porque o servidor reiniciou. Tente novamente."

POOL_MIN = 1
POOL_MAX = 10
POOL_TIMEOUT_ABERTURA = 10  # segundos para a primeira conexão

_DICA_URL = (
    "Configure a variável de ambiente DATABASE_URL com a URL do PostgreSQL, "
    "por exemplo postgresql://usuario:senha@localhost:5432/novamente."
)

# Chave do pg_advisory_xact_lock que serializa as migrações entre processos.
_CHAVE_LOCK_MIGRACAO = 5505501

_pool: ConnectionPool | None = None
_pool_url: str | None = None
_pool_lock = threading.Lock()  # só para abrir/trocar o pool uma vez
_esquema_pronto: set[str] = set()  # URLs cujo esquema já foi conferido


# ── Esquema e migrações ───────────────────────────────────────────────────────


def _migracao_v1(cursor: psycopg.Cursor) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS jobs (
            job_id TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            dados JSONB NOT NULL,
            expira_em TIMESTAMPTZ NOT NULL,
            atualizado_em TIMESTAMPTZ NOT NULL
        )
        """
    )
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_expira_em ON jobs (expira_em)")
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS pacotes (
            seq BIGINT GENERATED ALWAYS AS IDENTITY UNIQUE,
            adaptacao_id TEXT PRIMARY KEY,
            criado_em TIMESTAMPTZ NOT NULL,
            dados JSONB NOT NULL
        )
        """
    )


# Uma função por versão, aplicadas em ordem a partir de schema_version.
_MIGRACOES = {1: _migracao_v1}
VERSAO_ESQUEMA = max(_MIGRACOES)


def _garantir_esquema(conexao: psycopg.Connection, url: str) -> None:
    if url in _esquema_pronto:
        return
    with conexao.transaction(), conexao.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(%s)", (_CHAVE_LOCK_MIGRACAO,))
        cursor.execute("CREATE TABLE IF NOT EXISTS schema_version (versao INT NOT NULL)")
        atual = cursor.execute("SELECT coalesce(max(versao), 0) FROM schema_version").fetchone()[0]
        for proxima in range(atual + 1, VERSAO_ESQUEMA + 1):
            _MIGRACOES[proxima](cursor)
            cursor.execute("INSERT INTO schema_version (versao) VALUES (%s)", (proxima,))
    _esquema_pronto.add(url)


# ── Conexão ───────────────────────────────────────────────────────────────────


def mascarar_url(url: str) -> str:
    """URL sem a senha, para mensagens e logs."""
    try:
        partes = urlsplit(url)
        if partes.password:
            usuario = partes.username or ""
            host = partes.hostname or ""
            porta = f":{partes.port}" if partes.port else ""
            return urlunsplit(partes._replace(netloc=f"{usuario}:***@{host}{porta}"))
    except ValueError:
        pass  # porta ou IPv6 inválidos: mascara pelo texto, sem depender do urlsplit
    # ://usuario:senha@ (a senha pode conter '@' ou '/' sem codificação: vale o último '@')
    url = re.sub(r"(://[^:/\s]+:)\S*@", r"\1***@", url)
    return re.sub(r"(password\s*=\s*)\S+", r"\1***", url)


def _url() -> str:
    from app.core.config import settings  # lido a cada chamada: os testes trocam o valor

    url = settings.database_url.strip()
    if not url:
        raise RuntimeError(f"DATABASE_URL não definida. {_DICA_URL}")
    return url


def _validar_url(url: str) -> None:
    """Rejeita a URL que o libpq interpretaria de um jeito que expõe a senha.

    Senha com '@' sem codificação vira parte do host ('senha@host'); com '/',
    a URL é cortada e um trecho da senha vira a porta. Como os avisos do pool
    registram host e porta, a URL é recusada antes de o pool existir.
    """
    try:
        partes = conninfo_to_dict(url)
    except Exception:
        partes = None
    hosts = str((partes or {}).get("host") or "").split(",")
    portas = str((partes or {}).get("port") or "").split(",")
    if (
        partes is None
        or any("@" in host for host in hosts)
        or any(porta and not porta.isdigit() for porta in portas)
    ):
        raise RuntimeError(
            f"DATABASE_URL malformada ({mascarar_url(url)}). Se a senha tiver caracteres "
            "especiais (@, /, :, %, #, ?), codifique-os na URL: %40, %2F, %3A, %25, %23, %3F."
        ) from None


def _criar_pool(url: str) -> ConnectionPool:
    """Valida a URL, abre o pool e espera a primeira conexão; falha com a URL mascarada."""
    _validar_url(url)
    try:
        pool = ConnectionPool(url, min_size=POOL_MIN, max_size=POOL_MAX, open=False)
    except Exception:
        raise RuntimeError(
            f"DATABASE_URL inválida ({mascarar_url(url)}). {_DICA_URL}"
        ) from None
    try:
        pool.open(wait=True, timeout=POOL_TIMEOUT_ABERTURA)
    except Exception:
        pool.close()
        raise RuntimeError(
            f"Não foi possível conectar ao PostgreSQL em {mascarar_url(url)}. "
            f"Confira se o banco está no ar e a DATABASE_URL. {_DICA_URL}"
        ) from None
    return pool


def _obter_pool() -> tuple[ConnectionPool, str]:
    global _pool, _pool_url
    url = _url()
    with _pool_lock:
        if _pool is None or _pool_url != url:
            if _pool is not None:
                _pool.close()
            _pool, _pool_url = None, None
            _pool = _criar_pool(url)
            _pool_url = url
        return _pool, url


@contextmanager
def _conectar() -> Iterator[psycopg.Connection]:
    pool, url = _obter_pool()
    with pool.connection() as conexao:  # commit ao sair sem erro, rollback com erro
        _garantir_esquema(conexao, url)
        yield conexao


def encerrar() -> None:
    """Fecha o pool (shutdown do backend). A próxima operação abre outro."""
    global _pool, _pool_url
    with _pool_lock:
        if _pool is not None:
            _pool.close()
        _pool, _pool_url = None, None


def _instante(segundos: float) -> datetime:
    return datetime.fromtimestamp(segundos, timezone.utc)


def _agora_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Jobs ──────────────────────────────────────────────────────────────────────


def _gravar_job(conexao: psycopg.Connection, job: JobResposta, expira_em: float) -> None:
    conexao.execute(
        """
        INSERT INTO jobs (job_id, status, dados, expira_em, atualizado_em)
        VALUES (%s, %s, %s::jsonb, %s, %s)
        ON CONFLICT (job_id) DO UPDATE SET
            status = excluded.status,
            dados = excluded.dados,
            expira_em = excluded.expira_em,
            atualizado_em = excluded.atualizado_em
        """,
        (
            job.job_id,
            job.status,
            job.model_dump_json(),
            _instante(expira_em),
            datetime.fromisoformat(job.atualizado_em),
        ),
    )


def salvar_job(job: JobResposta, ttl_segundos: int = 1800) -> None:
    with _conectar() as conexao:
        _gravar_job(conexao, job, time.time() + ttl_segundos)


def obter_job(job_id: str) -> JobResposta | None:
    _purgar()
    with _conectar() as conexao:
        linha = conexao.execute("SELECT dados FROM jobs WHERE job_id = %s", (job_id,)).fetchone()
    return JobResposta.model_validate(linha[0]) if linha else None


def _purgar() -> None:
    with _conectar() as conexao:
        conexao.execute("DELETE FROM jobs WHERE expira_em < %s", (_instante(time.time()),))


# ── Pacotes ───────────────────────────────────────────────────────────────────


def salvar_pacote(pacote: AdaptacaoPacote) -> None:
    with _conectar() as conexao:
        conexao.execute(
            """
            INSERT INTO pacotes (adaptacao_id, criado_em, dados) VALUES (%s, %s, %s::jsonb)
            ON CONFLICT (adaptacao_id) DO UPDATE SET
                criado_em = excluded.criado_em,
                dados = excluded.dados
            """,
            (pacote.adaptacao_id, datetime.fromisoformat(pacote.criado_em), pacote.model_dump_json()),
        )


def obter_pacote(adaptacao_id: str) -> AdaptacaoPacote | None:
    with _conectar() as conexao:
        linha = conexao.execute(
            "SELECT dados FROM pacotes WHERE adaptacao_id = %s", (adaptacao_id,)
        ).fetchone()
    return AdaptacaoPacote.model_validate(linha[0]) if linha else None


def listar_pacotes() -> list[AdaptacaoPacote]:
    # ORDER BY seq mantém a ordem de criação (o upsert preserva o seq).
    with _conectar() as conexao:
        linhas = conexao.execute("SELECT dados FROM pacotes ORDER BY seq").fetchall()
    return [AdaptacaoPacote.model_validate(dados) for (dados,) in linhas]


# ── Subida ────────────────────────────────────────────────────────────────────


def iniciar() -> None:
    """Prepara o banco na subida do backend.

    Garante esquema e migrações, apaga jobs expirados e marca como ``failed``
    (código INTERNO) os jobs ``queued`` ou ``running`` que o processo anterior
    deixou para trás.
    """
    from app.core.config import settings

    _purgar()
    with _conectar() as conexao:
        pendentes = conexao.execute(
            "SELECT dados FROM jobs WHERE status IN ('queued', 'running') FOR UPDATE"
        ).fetchall()
        for (dados,) in pendentes:
            job = JobResposta.model_validate(dados)
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
