"""Preparo do arquivo SQLite na subida do backend.

Antes do ``create_all`` o backend confere os arquivos do banco: ``DB_PATH`` (jobs
e histórico) e o arquivo de ``DATABASE_URL`` (catálogo), que por padrão são o
mesmo. Com o volume vazio, a pasta e o arquivo são criados e o esquema nasce na
sequência. Se não der para gravar, a subida falha com uma mensagem que diz o que
conferir. Dados existentes nunca são alterados: a checagem de escrita abre uma
transação e a desfaz.
"""

from __future__ import annotations

import logging
import os
import sqlite3
import tempfile
from pathlib import Path

from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

logger = logging.getLogger(__name__)


def caminho_de_database_url(url: str) -> Path | None:
    """Arquivo SQLite de uma ``DATABASE_URL``, ou ``None`` se não houver arquivo.

    Aceita ``sqlite:///relativo.db`` e ``sqlite:////absoluto.db``. URLs de outros
    bancos, bancos em memória e URLs malformadas devolvem ``None``.
    """
    try:
        parsed = make_url(url)
    except ArgumentError:
        return None
    if not parsed.drivername.startswith("sqlite"):
        return None
    if parsed.database in (None, "", ":memory:") or parsed.database.startswith("file:"):
        return None
    return Path(parsed.database).expanduser()


def caminhos_do_banco(db_path: str, database_url: str) -> list[tuple[str, Path]]:
    """Pares ``(variável, caminho)`` dos arquivos distintos usados pelo backend."""
    candidatos: list[tuple[str, Path | None]] = [
        ("DB_PATH", Path(db_path).expanduser()),
        ("DATABASE_URL", caminho_de_database_url(database_url)),
    ]
    encontrados: list[tuple[str, Path]] = []
    vistos: set[Path] = set()
    for variavel, caminho in candidatos:
        if caminho is None:
            continue
        chave = caminho.resolve()
        if chave in vistos:
            continue
        vistos.add(chave)
        encontrados.append((variavel, caminho))
    return encontrados


def preparar_banco() -> None:
    """Garante pasta e arquivo graváveis para cada banco SQLite configurado.

    Levanta ``RuntimeError`` com texto em português quando a pasta não pode ser
    criada, o caminho aponta para uma pasta, não dá para gravar ou o arquivo não
    é um banco SQLite.
    """
    from app.core.config import settings  # lido a cada chamada: os testes trocam o valor

    for variavel, caminho in caminhos_do_banco(settings.db_path, settings.database_url):
        _preparar_arquivo(variavel, caminho)


def _preparar_arquivo(variavel: str, caminho: Path) -> None:
    pasta = caminho.parent
    try:
        pasta.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise RuntimeError(
            f"Não foi possível criar a pasta do banco de dados ({pasta}). "
            f"Confira se o volume está montado e se o usuário do backend pode gravar nele, "
            f"ou aponte {variavel} para outro caminho."
        ) from exc

    if caminho.is_dir():
        raise RuntimeError(
            f"{variavel} aponta para uma pasta ({caminho}), mas precisa apontar para um "
            "arquivo SQLite. Ajuste o valor, por exemplo para ./data/novamente.db."
        )

    # O WAL grava arquivos auxiliares ao lado do banco: a pasta precisa aceitar escrita.
    try:
        with tempfile.TemporaryFile(dir=pasta):
            pass
    except OSError as exc:
        raise RuntimeError(
            f"A pasta do banco de dados ({pasta}) não aceita gravação. "
            f"Confira as permissões da pasta (ou do volume) ou aponte {variavel} para outro caminho."
        ) from exc

    existia = caminho.exists()
    try:
        if not existia:
            caminho.touch()  # arquivo vazio: o SQLite o trata como banco novo
        # O SQLite abre arquivo somente leitura sem reclamar até a primeira gravação.
        if not os.access(caminho, os.W_OK):
            raise PermissionError(13, "sem permissão de escrita no arquivo")
        _testar_escrita(caminho)
    except (OSError, sqlite3.Error) as exc:
        raise RuntimeError(
            f"O arquivo do banco de dados ({caminho}) não pôde ser aberto para escrita "
            f"({exc}). Confira as permissões do arquivo e se ele é um banco SQLite válido; "
            f"o arquivo existente não foi alterado. Se preferir, aponte {variavel} para outro caminho."
        ) from exc

    if not existia:
        logger.info("Banco de dados novo: o arquivo foi criado e o esquema será criado na subida.")


def _testar_escrita(caminho: Path) -> None:
    """Pede o bloqueio de escrita e desfaz: confirma a escrita sem alterar dados."""
    conexao = sqlite3.connect(caminho, timeout=5, isolation_level=None)
    try:
        conexao.execute("PRAGMA schema_version").fetchone()  # lê o cabeçalho: acusa arquivo que não é banco
        conexao.execute("BEGIN IMMEDIATE")
        conexao.execute("ROLLBACK")
    finally:
        conexao.close()
