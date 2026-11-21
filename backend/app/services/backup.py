"""Backup consistente do SQLite e retenção dos arquivos gerados.

Usa a API de backup do ``sqlite3``: a cópia é um retrato consistente do banco
mesmo com o backend gravando, sem parar o serviço. A origem é aberta em modo
leitura e a cópia passa por um arquivo temporário na própria pasta de destino,
renomeado só depois de verificado (``integrity_check`` e contagem de tabelas).

Só o SQLite entra no backup. O índice do ChromaDB é descartável e não é copiado.
"""

from __future__ import annotations

import os
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

PREFIXO = "novamente-"
FORMATO_DATA = "%Y%m%d-%H%M%S"
# Único padrão de nome que a retenção reconhece; qualquer outro arquivo da pasta é ignorado.
PADRAO_NOME = re.compile(r"^novamente-\d{8}-\d{6}\.db$")


class ErroBackup(Exception):
    """Falha ao gerar ou verificar o backup. A mensagem é segura para exibir."""


class ErroRetencao(Exception):
    """O backup foi gerado, mas a retenção não conseguiu apagar algum arquivo antigo."""


@dataclass(frozen=True)
class ResultadoBackup:
    arquivo: Path
    tamanho_bytes: int
    tabelas: int


def nome_do_backup(momento: datetime) -> str:
    """``novamente-AAAAMMDD-HHMMSS.db`` na hora UTC do momento informado."""
    return f"{PREFIXO}{momento.astimezone(timezone.utc).strftime(FORMATO_DATA)}.db"


def listar_backups(pasta: Path) -> list[Path]:
    """Backups da pasta, do mais antigo para o mais recente (a data está no nome)."""
    if not pasta.is_dir():
        return []
    return sorted(
        entrada
        for entrada in pasta.iterdir()
        if PADRAO_NOME.match(entrada.name) and entrada.is_file() and not entrada.is_symlink()
    )


def gerar_backup(origem: Path, pasta: Path, *, momento: datetime | None = None) -> ResultadoBackup:
    """Copia ``origem`` para ``pasta/novamente-AAAAMMDD-HHMMSS.db`` e confere o resultado.

    O arquivo final só aparece depois de passar nas verificações; em caso de
    falha o temporário é removido e a pasta fica como estava.
    """
    momento = momento or datetime.now(timezone.utc)
    if not origem.is_file():
        raise ErroBackup("Banco de dados não encontrado. Confira DB_PATH e se o volume está montado.")
    try:
        pasta.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ErroBackup(
            "Não foi possível criar a pasta de backup. Confira BACKUP_DIR e as permissões do volume."
        ) from exc

    final = pasta / nome_do_backup(momento)
    if final.exists():
        raise ErroBackup("Já existe um backup com este horário (segundo). Tente de novo em instantes.")
    temporario = pasta / f".{final.name}.{os.getpid()}.tmp"  # não casa com PADRAO_NOME

    try:
        _copiar(origem, temporario)
        tabelas = _verificar(temporario)
        os.chmod(temporario, 0o600)  # o banco tem dados de alunos
        os.replace(temporario, final)
    except sqlite3.Error as exc:
        raise ErroBackup(f"O SQLite recusou o backup ({exc}).") from exc
    except OSError as exc:
        raise ErroBackup(
            f"Falha ao gravar o backup ({type(exc).__name__}). Confira BACKUP_DIR, o espaço em disco "
            "e as permissões."
        ) from exc
    finally:
        temporario.unlink(missing_ok=True)

    return ResultadoBackup(arquivo=final, tamanho_bytes=final.stat().st_size, tabelas=tabelas)


def _copiar(origem: Path, destino: Path) -> None:
    # Modo leitura: o backup nunca escreve no banco de produção nem o cria se faltar.
    # A cópia é feita num passo só, para um gravador concorrente não reiniciá-la.
    fonte = sqlite3.connect(f"{origem.resolve().as_uri()}?mode=ro", uri=True, timeout=30)
    try:
        copia = sqlite3.connect(destino)
        try:
            fonte.backup(copia)
            # Arquivo único e autocontido, sem depender de -wal/-shm ao restaurar.
            copia.execute("PRAGMA journal_mode=DELETE").fetchone()
        finally:
            copia.close()
    finally:
        fonte.close()
    with open(destino, "rb") as arquivo:
        os.fsync(arquivo.fileno())


def _verificar(arquivo: Path) -> int:
    """Confere integridade e conta as tabelas; levanta ``ErroBackup`` se algo estiver errado."""
    conexao = sqlite3.connect(f"{arquivo.resolve().as_uri()}?mode=ro", uri=True)
    try:
        resultado = conexao.execute("PRAGMA integrity_check").fetchall()
        if resultado != [("ok",)]:
            raise ErroBackup("A verificação de integridade do backup falhou; o arquivo foi descartado.")
        (tabelas,) = conexao.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        ).fetchone()
    finally:
        conexao.close()
    if tabelas == 0:
        raise ErroBackup(
            "O banco de origem não tem tabelas; o backup foi descartado. Confira se DB_PATH aponta "
            "para o banco em uso."
        )
    return tabelas


def aplicar_retencao(pasta: Path, manter: int) -> list[Path]:
    """Apaga os backups mais antigos e mantém os ``manter`` mais recentes.

    Só mexe em arquivos que casam exatamente com ``PADRAO_NOME``. Devolve os
    arquivos removidos. Se algum não puder ser apagado, os demais são tentados e
    ``ErroRetencao`` é levantada no fim.
    """
    if manter < 1:
        raise ValueError("A retenção mínima é 1 backup.")
    backups = listar_backups(pasta)
    excedentes = backups[: max(len(backups) - manter, 0)]
    removidos: list[Path] = []
    falhas = 0
    for arquivo in excedentes:
        try:
            arquivo.unlink()
            removidos.append(arquivo)
        except OSError:
            falhas += 1
    if falhas:
        raise ErroRetencao(
            f"{falhas} backup(s) antigo(s) não puderam ser apagados. Confira as permissões de BACKUP_DIR."
        )
    return removidos
